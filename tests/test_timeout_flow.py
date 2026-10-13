"""SDK failure diagnostics and batch lifecycle, using fake clients only."""
import base64
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from openai import (APITimeoutError, APIConnectionError, APIStatusError, AuthenticationError,
                    PermissionDeniedError, BadRequestError, RateLimitError, InternalServerError,
                    APIResponseValidationError)

from main import main
from src.desktop_app import DesktopApp
from src.execution_state import Journal, digest
from src.excel_reader import load_queue
from src.generation_errors import classify_exception, sanitize_diagnostic
from src.image_generator import GenerationError, OpenAIImageGenerator
from src.studio_session import StudioSession, RunControl
from support import IsolatedTest, png_bytes
import test_stage_three as fixtures


class TimeoutFlowTests(IsolatedTest):
    def setUp(self):
        super().setUp()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.queue, _, self.output = fixtures.StageThreeTests().make_queue(self.root,
            [[i, f'Produto {i}', '', 'ok.png', f'{i}.png', 'PENDENTE', 0, ''] for i in range(1, 11)])
        self.env = dict(IMAGE_PROVIDER='openai', DRY_RUN='NAO', FIRST_RUN_SAFE_MODE='NAO',
                        MAX_JOBS_PER_RUN='10', MAX_IMAGES_PER_RUN='10')
        self.edit = Mock(side_effect=self.response)
        self.sleep = Mock()
        self.generator = OpenAIImageGenerator(client=SimpleNamespace(images=SimpleNamespace(edit=self.edit)),
                                             timeout=120, retries=2, sleep=self.sleep)
        self.request = httpx.Request('POST', 'https://example.test',
                                    headers={'Authorization': 'Bearer NEVER_LOG_THIS'}, content=b'PRIVATE_PAYLOAD')

    def response(self, **kwargs):
        return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(png_bytes()).decode())
                                     for _ in range(kwargs['n'])], _request_id='req_fake_success')

    def run_queue(self, control=None):
        return main(self.queue, env=self.env, generator=self.generator, control=control)

    def session(self):
        session = StudioSession(self.root / 'settings.json', allow_api=True, env={})
        session.choose_queue(self.queue)
        values = deepcopy(session.preferences)
        values.update(max_jobs=10, max_images=10, safe_mode=False, timeout=120)
        values['image']['quality'] = 'max'
        session.set_preferences(values)
        session._session_api_key = 'isolated-fake-key'
        return session

    def test_timeout_stops_first_call_and_resume_never_resends_review(self):
        exc = APITimeoutError(request=self.request)
        exc.__cause__ = RuntimeError('NEVER_LOG_THIS PRIVATE_PAYLOAD')
        self.edit.side_effect = exc
        with self.assertLogs('gerador_imagens', 'INFO') as logged:
            result = self.run_queue()
        self.assertEqual((result['planned'], result['started'], result['completed'], result['review'], result['waiting']),
                         (10, 1, 0, 1, 9))
        self.assertEqual(result['stop_reason'], 'Interrompido para revisão após timeout')
        self.assertEqual(self.edit.call_count, 1)
        self.sleep.assert_not_called()
        self.assertEqual(load_queue(self.queue)['Status'].tolist(), ['REVISAO'] + ['PENDENTE'] * 9)
        error = Journal(self.queue).records['1']['error']
        self.assertEqual((error['category'], error['exception_type'], error['timeout_seconds'], error['api_attempts']),
                         ('timeout', 'APITimeoutError', 120, 1))
        self.assertTrue(error['uncertain'])
        self.assertGreaterEqual(error['elapsed_seconds'], 0)
        self.assertFalse(list(self.output.glob('*.png')))
        for text in ('NEVER_LOG_THIS', 'PRIVATE_PAYLOAD', 'Authorization'):
            self.assertNotIn(text, '\n'.join(logged.output) + Journal(self.queue).path.read_text('utf-8'))
        self.edit.side_effect = self.response
        self.run_queue()
        self.assertEqual(self.edit.call_count, 10)  # Nine pending items; item 1 is never resent.
        self.assertEqual(load_queue(self.queue).iloc[0]['Status'], 'REVISAO')
        self.assertEqual(Journal(self.queue).records['1']['api_attempts'], 1)

    def test_connection_is_distinct_from_timeout_and_stops_batch(self):
        self.edit.side_effect = APIConnectionError(request=self.request, message='NEVER_LOG_THIS')
        result = self.run_queue()
        error = Journal(self.queue).records['1']['error']
        self.assertEqual((error['category'], error['exception_type']), ('connection', 'APIConnectionError'))
        self.assertIn('conexão', result['stop_reason'])
        self.assertEqual(self.edit.call_count, 1)
        self.sleep.assert_not_called()

    def test_http_categories_known_codes_request_ids_and_no_raw_payload(self):
        cases = [(AuthenticationError, 401, 'invalid_api_key', 'authentication', False),
                 (PermissionDeniedError, 403, 'permission_denied', 'permission', False),
                 (BadRequestError, 400, 'invalid_value', 'parameters', False),
                 (RateLimitError, 429, 'insufficient_quota', 'limit_quota', False),
                 (InternalServerError, 500, 'private-unknown-code', 'server', True),
                 (InternalServerError, 503, 'server_is_overloaded', 'server', False),
                 (APIStatusError, 408, 'private-unknown-code', 'timeout', True)]
        for cls, status, code, category, uncertain in cases:
            with self.subTest(status=status):
                exc = cls('NEVER_LOG_THIS', response=httpx.Response(status, request=self.request,
                    headers={'x-request-id': 'req_fake_error', 'private': 'NEVER_LOG_THIS'}),
                    body={'code': code, 'message': 'PRIVATE_PAYLOAD'})
                details = classify_exception(exc, timeout=120, attempts=1, elapsed=0.5)
                self.assertEqual((details['category'], details['uncertain'], details['http_status']),
                                 (category, uncertain, status))
                self.assertEqual(details['request_id'], 'req_fake_error')
                self.assertEqual(details.get('api_code'), code if code != 'private-unknown-code' else None)
                self.assertNotIn('NEVER_LOG_THIS', json.dumps(details))
                self.assertNotIn('PRIVATE_PAYLOAD', json.dumps(details))
        invalid = APIResponseValidationError(response=httpx.Response(200, request=self.request,
            headers={'x-request-id': 'req_invalid_response'}), body={'message': 'PRIVATE_PAYLOAD'})
        details = classify_exception(invalid, timeout=120, attempts=1)
        self.assertEqual((details['category'], details['http_status'], details['request_id']),
                         ('invalid_image', 200, 'req_invalid_response'))
        self.assertTrue(details['uncertain'])
        self.assertNotIn('PRIVATE_PAYLOAD', json.dumps(details))

    def test_unexpected_exception_is_safe_and_stops_following_item(self):
        self.edit.side_effect = RuntimeError('NEVER_LOG_THIS')
        result = self.run_queue()
        details = Journal(self.queue).records['1']['error']
        self.assertEqual((details['category'], details['exception_type']), ('unexpected', 'RuntimeError'))
        self.assertEqual((result['started'], result['review'], result['waiting']), (1, 1, 9))
        self.assertNotIn('NEVER_LOG_THIS', Journal(self.queue).path.read_text('utf-8'))

    def test_stop_during_safe_retry_wait_does_not_make_another_call(self):
        exc = InternalServerError('PRIVATE_PAYLOAD', response=httpx.Response(503, request=self.request),
                                  body={'code': 'server_is_overloaded'})
        self.edit.side_effect = exc
        control = RunControl(lambda *args: None)
        self.sleep.side_effect = lambda seconds: control.command('stop')
        result = self.run_queue(control)
        self.assertEqual(self.edit.call_count, 1)
        self.assertEqual(result['stop_reason'], 'Interrompido por solicitação do usuário')
        self.assertEqual((result['review'], result['waiting']), (0, 9))

    def test_stop_during_inflight_call_remains_active_then_saves_current_result(self):
        session = self.session()
        entered, release = threading.Event(), threading.Event()
        def blocked(**kwargs):
            entered.set()
            if not release.wait(5):
                raise AssertionError('Test did not release its fake call')
            return self.response(**kwargs)
        self.edit.side_effect = blocked
        fake = SimpleNamespace(images=SimpleNamespace(edit=self.edit))
        with patch('openai.OpenAI', return_value=fake), patch.object(session.credential_store, 'read',
                side_effect=AssertionError('Credential reads forbidden')):
            session.start(real=True)
            try:
                self.assertTrue(entered.wait(3))
                session.command('stop')
                state = session.state()
                self.assertTrue(state['active'])
                self.assertTrue(state['stopping'])
                self.assertIn('aguardando', state['status'])
                with self.assertRaisesRegex(ValueError, 'Interrupção já solicitada'):
                    session.command('resume')
                self.assertIsNone(state['run_log']['finished_at'])
                self.assertEqual(self.edit.call_count, 1)
            finally:
                release.set()
                session.worker.join(5)
        self.assertFalse(session.active)
        self.assertEqual(session.result['success'], 1)
        self.assertEqual(session.run_log['counts'], dict(planned=10, started=1, completed=1, review=0, waiting=9, errors=0))
        self.assertEqual(self.edit.call_count, 1)
        self.assertEqual(load_queue(self.queue)['Status'].tolist(), ['CONCLUIDO'] + ['PENDENTE'] * 9)

    def test_session_automatic_timeout_persists_diagnostics_counts_and_final_reason(self):
        session = self.session()
        self.edit.side_effect = APITimeoutError(request=self.request)
        with patch('openai.OpenAI', return_value=SimpleNamespace(images=SimpleNamespace(edit=self.edit))) as client:
            session.start(real=True)
            session.worker.join(5)
        self.assertFalse(session.active)
        self.assertEqual(self.edit.call_count, 1)
        self.assertEqual(client.call_args.kwargs['max_retries'], 0)
        self.assertEqual(client.call_args.kwargs['timeout'], 120)
        stored = json.loads(Path(str(self.queue) + '.studio-run.json').read_text('utf-8'))
        self.assertEqual(stored['status'], 'Interrompido para revisão após timeout')
        self.assertEqual(stored['counts'], dict(planned=10, started=1, completed=0, review=1, waiting=9, errors=0))
        event = next(event for event in stored['events'] if event['type'] == 'item_end')
        self.assertEqual(event['diagnostic']['category'], 'timeout')
        self.assertEqual(event['diagnostic']['timeout_seconds'], 120)
        self.assertEqual(event['api_attempts'], 1)

    def test_desktop_close_waits_for_timeout_and_persisted_history(self):
        session = self.session()
        entered, release, destroyed = threading.Event(), threading.Event(), threading.Event()
        def blocked(**kwargs):
            entered.set()
            release.wait(5)
            raise APITimeoutError(request=self.request)
        self.edit.side_effect = blocked
        app = DesktopApp(session, SimpleNamespace())
        app.window = Mock()
        app.window.create_confirmation_dialog.return_value = True
        def destroy():
            stored = json.loads(Path(str(self.queue) + '.studio-run.json').read_text('utf-8'))
            self.assertEqual(stored['counts']['review'], 1)
            self.assertIsNotNone(stored['finished_at'])
            self.assertFalse(session.active)
            destroyed.set()
        app.window.destroy.side_effect = destroy
        with patch('openai.OpenAI', return_value=SimpleNamespace(images=SimpleNamespace(edit=self.edit))):
            session.start(real=True)
            try:
                self.assertTrue(entered.wait(3))
                self.assertFalse(app.on_closing())
                self.assertFalse(destroyed.wait(.03))
                self.assertTrue(session.active)
                self.assertIn('não confirma cancelamento remoto', app.window.create_confirmation_dialog.call_args.args[1])
            finally:
                release.set()
                session.worker.join(5)
            self.assertTrue(destroyed.wait(3))
        self.assertEqual(self.edit.call_count, 1)

    def test_legacy_history_load_and_saved_timeout_are_unchanged(self):
        path = Path(str(self.queue) + '.studio-run.json')
        legacy = dict(version=1, planned_items=10, status='Interrompido', result={'processed': 3, 'success': 0},
                      events=[{'type': 'item_end', 'id': '1', 'status': 'REVISAO'}])
        path.write_text(json.dumps(legacy), 'utf-8')
        before = digest(path)
        session = self.session()
        self.assertEqual(session.state()['run_log'], legacy)
        self.assertEqual(digest(path), before)
        preferences = deepcopy(session.preferences)
        session.set_preferences(preferences, persist=True)
        reopened = StudioSession(session.settings_path, env={})
        self.assertEqual(reopened.preferences, preferences)
        self.assertEqual((reopened.preferences['image']['quality'], reopened.preferences['timeout']), ('max', 120))

    def test_sanitizer_rejects_sensitive_codes_request_ids_and_fields(self):
        details = sanitize_diagnostic({'category': 'timeout', 'exception_type': 'RuntimeError',
            'api_code': 'NEVER_LOG_THIS', 'request_id': 'sk-secret-value', 'body': 'PRIVATE_PAYLOAD',
            'headers': {'Authorization': 'NEVER_LOG_THIS'}, 'timeout_seconds': 120})
        self.assertNotIn('api_code', details)
        self.assertNotIn('request_id', details)
        self.assertNotIn('body', details)
        self.assertNotIn('headers', details)
