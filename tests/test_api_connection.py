import http.client
import json
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import httpx
from openai import OpenAI as RealOpenAI

from src.api_connection import check_api_connection
from src.studio_session import StudioSession
from studio import make_server
from support import IsolatedTest


KEY = 'sk-test-placeholder-only-1234567890'


class ConnectionTests(IsolatedTest):
    def setUp(self):
        super().setUp()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.session = StudioSession(Path(self.temp.name) / 'preferences.json', env={})

    def campaign(self, *, key=KEY):
        from test_stage_three import StageThreeTests
        root = Path(tempfile.mkdtemp(dir=self.temp.name))
        queue, refs, output = StageThreeTests().make_queue(root,
            [[1, 'Foto de produto', '', 'ok.png', 'produto.png', 'PENDENTE', 0, '']])
        session = StudioSession(root / 'settings.json', allow_api=True,
                                env={'OPENAI_API_KEY': key} if key else {})
        session.choose_queue(queue)
        session.set_folders([{'alias': 'Produtos', 'path': str(refs)}], 'Produtos')
        session.set_preferences({**session.preferences, 'output_dir': str(output), 'safe_mode': False})
        return session, queue

    def test_real_start_checks_once_in_background_before_generation(self):
        session, _ = self.campaign()
        entered, finish = threading.Event(), threading.Event()

        def probe(key):
            self.assertEqual(key, KEY)
            entered.set()
            finish.wait(5)
            return dict(status='connected', message='Autenticação confirmada.')

        def generate(*args, **kwargs):
            self.assertEqual(session.state()['api_connection']['status'], 'connected')
            self.assertEqual(kwargs['env']['OPENAI_API_KEY'], KEY)
            return dict(success=0, errors=0, processed=0)

        with patch('src.api_connection.check_api_connection', side_effect=probe) as check, \
                patch('main.main', side_effect=generate) as run:
            try:
                session.start(real=True)
                self.assertTrue(entered.wait(2))
                state = session.state()
                self.assertTrue(state['active'])
                self.assertEqual(state['api_connection']['status'], 'checking')
                run.assert_not_called()
                with self.assertRaises(ValueError):
                    session.start(real=True)
                with self.assertRaises(ValueError):
                    session.set_api_key('fictional-new-key-only')
            finally:
                finish.set()
                session.worker.join(5)
            check.assert_called_once_with(KEY)
            run.assert_called_once()
        self.assertEqual(session.state()['api_connection']['status'], 'connected')
        self.assertTrue(session.state()['api_connection']['checked_at'])
        self.assertNotIn(KEY, json.dumps(session.state()))

    def test_preview_and_simulation_do_not_probe(self):
        session, _ = self.campaign()
        with patch('src.api_connection.check_api_connection') as check:
            session.validate_campaign()
            session.start()
            session.worker.join(5)
        check.assert_not_called()
        self.assertEqual(session.state()['api_connection']['status'], 'unverified')

    def test_authentication_failure_or_missing_key_stops_before_generation(self):
        import hashlib
        for key in (KEY, None):
            with self.subTest(key_present=bool(key)):
                session, queue = self.campaign(key=key)
                before = hashlib.sha256(queue.read_bytes()).digest()
                with patch('src.api_connection.check_api_connection', return_value=dict(
                        status='disconnected', category='authentication', message='Autenticação recusada.')) as check, \
                        patch('main.main') as run:
                    session.start(real=True)
                    session.worker.join(5)
                    run.assert_not_called()
                    self.assertEqual(check.call_count, int(bool(key)))
                self.assertEqual(session.state()['api_connection']['status'], 'disconnected')
                self.assertEqual(hashlib.sha256(queue.read_bytes()).digest(), before)
                self.assertFalse(session.active)
                self.assertFalse(session.run_log['events'])
                self.assertNotIn(KEY, json.dumps(session.state()))

    def test_inconclusive_probe_does_not_block_image_only_key(self):
        for category in ('permission', 'limited', 'provider'):
            with self.subTest(category=category):
                session, _ = self.campaign()
                with patch('src.api_connection.check_api_connection', return_value=dict(
                        status='unverified', category=category, message='Verificação inconclusiva.')), \
                        patch('main.main', return_value=dict(success=0, errors=0, processed=0)) as run:
                    session.start(real=True)
                    session.worker.join(5)
                    run.assert_called_once()
                self.assertEqual(session.state()['api_connection']['status'], 'unverified')

    def test_generation_success_confirms_connection_after_inconclusive_probe(self):
        session, _ = self.campaign()

        def generate(*args, control, **kwargs):
            control.event('item_start', id='1')
            control.event('item', id='1', status='CONCLUIDO', message='Sucesso fictício.', api_attempts=1)
            return dict(success=1, errors=0, processed=1)

        with patch('src.api_connection.check_api_connection', return_value=dict(
                status='unverified', category='permission', message='Sem permissão de listar modelos.')), \
                patch('main.main', side_effect=generate):
            session.start(real=True)
            session.worker.join(5)
        self.assertEqual(session.state()['api_connection']['status'], 'connected')
        self.assertIn('geração', session.state()['api_connection']['message'])

    def test_generation_errors_do_not_confuse_authentication_with_content_or_quota(self):
        for status, category, code in ((401, 'authentication', 'invalid_api_key'),
                (400, 'parameters', 'moderation_blocked'), (429, 'limit_quota', 'insufficient_quota'),
                (None, 'timeout', None), (None, 'storage', None)):
            with self.subTest(category=category):
                session, _ = self.campaign()

                def generate(*args, control, **kwargs):
                    control.event('item', id='1', status='ERRO', message='Falha fictícia.',
                        diagnostic=dict(category=category, http_status=status, api_code=code))
                    return dict(success=0, errors=1, processed=1)

                with patch('src.api_connection.check_api_connection', return_value=dict(
                        status='connected', message='Autenticação confirmada.')), \
                        patch('main.main', side_effect=generate):
                    session.start(real=True)
                    session.worker.join(5)
                expected = 'disconnected' if status == 401 else 'connected'
                self.assertEqual(session.state()['api_connection']['status'], expected)

    def test_failed_probe_never_stays_checking_or_leaks_exception(self):
        session, _ = self.campaign()
        with patch('src.api_connection.check_api_connection', side_effect=RuntimeError(KEY)), \
                patch('main.main', return_value=dict(success=0, errors=0, processed=0)):
            session.start(real=True)
            session.worker.join(5)
        self.assertEqual(session.state()['api_connection']['status'], 'unverified')
        self.assertNotIn(KEY, json.dumps(session.state()))

    def test_unreadable_saved_key_during_start_does_not_probe_or_generate(self):
        session, _ = self.campaign()
        with patch.object(session.credential_store, 'read', side_effect=OSError(KEY)), \
                patch('src.api_connection.check_api_connection') as check, patch('main.main') as run:
            session.start(real=True)
            session.worker.join(5)
        check.assert_not_called()
        run.assert_not_called()
        self.assertEqual(session.state()['api_connection']['status'], 'disconnected')
        self.assertNotIn(KEY, json.dumps(session.state()))

    def test_start_during_manual_probe_is_rejected_without_second_check(self):
        session, _ = self.campaign()
        entered, finish = threading.Event(), threading.Event()

        def probe(key):
            entered.set()
            finish.wait(5)
            return dict(status='connected', message='OK')

        with patch('src.api_connection.check_api_connection', side_effect=probe) as check:
            try:
                session.verify_api_key()
                self.assertTrue(entered.wait(2))
                with self.assertRaisesRegex(ValueError, 'verificação'):
                    session.start(real=True)
                self.assertIsNone(session.worker)
            finally:
                finish.set()
                session.connection_worker.join(5)
            check.assert_called_once_with(KEY)

    def probe(self, response):
        requests = []

        def transport(request):
            requests.append(request)
            self.assertEqual(str(request.url), 'https://api.openai.com/v1/models')
            self.assertEqual(request.method, 'GET')
            self.assertEqual(request.headers['Authorization'], 'Bearer ' + KEY)
            self.assertEqual(request.read(), b'')
            if isinstance(response, Exception):
                raise response
            return response

        def factory(**kwargs):
            self.assertEqual(kwargs['max_retries'], 0)
            self.assertEqual(kwargs['timeout'], 10)
            return RealOpenAI(http_client=httpx.Client(transport=httpx.MockTransport(transport)), **kwargs)

        with patch('openai.OpenAI', side_effect=factory):
            result = check_api_connection(KEY)
        self.assertEqual(len(requests), 1)
        self.assertNotIn(KEY, json.dumps(result))
        self.assertNotIn('secret response', json.dumps(result))
        return result

    def test_official_read_only_probe_ignores_base_url_override(self):
        with patch.dict('os.environ', {'OPENAI_BASE_URL': 'https://untrusted.invalid/v1'}):
            result = self.probe(httpx.Response(200, json={'object': 'list', 'data': []}))
        self.assertEqual(result['status'], 'connected')

    def test_provider_errors_are_distinct_and_never_expose_response(self):
        cases = ((401, 'Autenticação'), (403, 'permissão'), (429, 'limitou'), (500, 'não pôde'))
        for status, message in cases:
            with self.subTest(status=status):
                result = self.probe(httpx.Response(status, json={'error': {
                    'message': KEY + ' secret response', 'type': 'test', 'code': 'test'}}))
                self.assertEqual(result['status'], 'disconnected' if status == 401 else 'unverified')
                self.assertIn(message, result['message'])

    def test_timeout_and_network_errors_do_not_mark_key_invalid_or_retry(self):
        request = httpx.Request('GET', 'https://api.openai.com/v1/models')
        for error, message in ((httpx.ReadTimeout(KEY, request=request), 'demorou'),
                               (httpx.ConnectError(KEY, request=request), 'conexão')):
            with self.subTest(error=type(error).__name__):
                result = self.probe(error)
                self.assertEqual(result['status'], 'disconnected')
                self.assertIn(message, result['message'])

    def test_missing_and_unreadable_key_do_not_contact_provider(self):
        with patch('src.api_connection.check_api_connection') as probe:
            self.assertEqual(self.session.verify_api_key()['status'], 'disconnected')
            self.assertIsNone(self.session.connection_worker)
            with patch.object(self.session.credential_store, 'read', side_effect=OSError(KEY)):
                result = self.session.verify_api_key()
            self.assertIn('protegida', result['message'])
            self.assertNotIn(KEY, json.dumps(result))
            probe.assert_not_called()

    def test_background_check_remains_responsive_and_deduplicates(self):
        started, finish = threading.Event(), threading.Event()
        self.session.set_api_key(KEY)

        def probe(key):
            self.assertEqual(key, KEY)
            started.set()
            finish.wait(3)
            return dict(status='connected', message='Autenticação confirmada.')

        with patch('src.api_connection.check_api_connection', side_effect=probe) as check:
            try:
                self.assertEqual(self.session.verify_api_key()['status'], 'checking')
                self.assertTrue(started.wait(2))
                self.assertEqual(self.session.state()['api_connection']['status'], 'checking')
                self.session.verify_api_key()
                self.assertEqual(check.call_count, 1)
            finally:
                finish.set()
                self.session.connection_worker.join(3)
        state = self.session.state()
        self.assertEqual(state['api_connection']['status'], 'connected')
        self.assertTrue(state['api_connection']['checked_at'])
        self.assertNotIn(KEY, json.dumps(state))
        self.assertFalse(self.session.settings_path.exists())
        reopened = StudioSession(self.session.settings_path, env={})
        self.assertEqual(reopened.state()['api_connection']['status'], 'unverified')

    def test_late_response_cannot_validate_replaced_or_removed_key(self):
        for remove in (False, True):
            with self.subTest(remove=remove):
                finish, started = threading.Event(), threading.Event()
                self.session.set_api_key(KEY)

                def probe(key):
                    started.set()
                    finish.wait(3)
                    return dict(status='connected', message='Confirmed')

                with patch('src.api_connection.check_api_connection', side_effect=probe):
                    self.session.verify_api_key()
                    self.assertTrue(started.wait(2))
                    old_worker = self.session.connection_worker
                    # Simulate a superseded probe (normal UI/backend mutations
                    # are blocked while checking); revision remains defense in depth.
                    self.session._reset_api_connection()
                    if remove:
                        self.session.clear_api_key()
                    else:
                        self.session.set_api_key('sk-new-placeholder-only-1234567890')
                    finish.set()
                    old_worker.join(3)
                self.assertEqual(self.session.state()['api_connection']['status'], 'unverified')

    def test_external_key_resolves_fresh_and_saved_session_key_has_priority(self):
        self.session.env = {'OPENAI_API_KEY': KEY}
        with patch('src.api_connection.check_api_connection', return_value=dict(status='connected', message='OK')) as probe:
            self.session.verify_api_key()
            self.session.connection_worker.join(3)
            probe.assert_called_once_with(KEY)
            self.session.set_api_key('sk-session-placeholder-only-1234567890')
            self.session.verify_api_key()
            self.session.connection_worker.join(3)
            self.assertEqual(probe.call_args.args[0], 'sk-session-placeholder-only-1234567890')
        self.assertFalse(self.session.allow_api)

    def test_check_during_campaign_is_rejected(self):
        self.session.active = True
        with self.assertRaisesRegex(ValueError, 'ativa'), patch('src.api_connection.check_api_connection') as probe:
            self.session.verify_api_key()
        probe.assert_not_called()

    def test_http_save_never_probes_and_explicit_check_requires_local_auth(self):
        server = make_server(self.session)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        def request(path, data, authorized=True, origin=None):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            headers = {'Content-Type': 'application/json'}
            if authorized:
                headers['X-Afirma-Token'] = server.session_token
            if origin:
                headers['Origin'] = origin
            connection.request('POST', path, body=json.dumps(data), headers=headers)
            response = connection.getresponse()
            result = response.status, response.read().decode()
            connection.close()
            self.assertNotIn(KEY, result[1])
            return result

        with patch('src.api_connection.check_api_connection', return_value=dict(status='connected', message='OK')) as probe:
            self.assertEqual(request('/api/credential/check', {}, authorized=False)[0], 403)
            self.assertEqual(request('/api/credential/check', {}, origin='https://untrusted.invalid')[0], 403)
            probe.assert_not_called()
            self.assertEqual(request('/api/credential', {'key': KEY})[0], 200)
            self.assertIsNone(self.session.connection_worker)
            probe.assert_not_called()
            self.assertEqual(self.session.state()['api_connection']['status'], 'unverified')
            self.assertEqual(request('/api/credential/check', {})[0], 200)
            self.session.connection_worker.join(3)
            self.assertEqual(probe.call_count, 1)

    def test_replacement_failure_preserves_key_and_verification_without_leaking(self):
        self.session.set_api_key(KEY)
        with patch('src.api_connection.check_api_connection', return_value=dict(status='connected', message='OK')):
            self.session.verify_api_key()
            self.session.connection_worker.join(3)
        with patch.object(self.session.credential_store, 'save', side_effect=OSError(KEY)):
            with self.assertRaises(ValueError) as raised:
                self.session.set_api_key('fictional-replacement-value-only', persist=True)
        self.assertNotIn(KEY, str(raised.exception))
        self.assertEqual(self.session.resolve_api_key(), KEY)
        self.assertEqual(self.session.state()['api_connection']['status'], 'connected')
        self.session.set_api_key('fictional-replacement-value-only')
        self.assertEqual(self.session.state()['api_connection']['status'], 'unverified')

    def test_removal_is_scoped_and_reveals_lower_priority(self):
        self.session._external_api_key_available = True
        self.session.set_api_key(KEY, persist=True)
        self.session.set_api_key('fictional-session-value-only')
        self.session.clear_api_key('session')
        self.assertEqual(self.session.api_key_status(), 'saved')
        self.assertEqual(self.session.resolve_api_key(), KEY)
        self.session.set_api_key('fictional-session-value-only')
        self.session.clear_api_key('saved')
        self.assertEqual(self.session.api_key_status(), 'session')
        self.session.clear_api_key('session')
        self.assertEqual(self.session.api_key_status(), 'external')
        with self.assertRaises(ValueError):
            self.session.clear_api_key('external')
        self.session._external_api_key_available = False
        self.assertEqual(self.session.api_key_status(), 'missing')

    def test_mutations_blocked_while_checking_or_running(self):
        self.session.set_api_key(KEY)
        for active, status in ((True, 'unverified'), (False, 'checking')):
            self.session.active = active
            self.session._api_connection['status'] = status
            with self.assertRaises(ValueError):
                self.session.set_api_key('fictional-replacement-value-only')
            with self.assertRaises(ValueError):
                self.session.clear_api_key('session')
            self.assertEqual(self.session.resolve_api_key(), KEY)

    def test_lan_cannot_trigger_credential_probe(self):
        from http.server import ThreadingHTTPServer
        with patch('studio.ThreadingHTTPServer', side_effect=lambda address, handler:
                   ThreadingHTTPServer(('127.0.0.1', 0), handler)):
            server = make_server(self.session, host='192.168.1.2')
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
        headers = {'Host': f'192.168.1.2:{server.server_port}',
                   'X-Afirma-Token': server.session_token,
                   'Cookie': 'afirma_access=' + server.access_key, 'Content-Type': 'application/json'}
        with patch('src.api_connection.check_api_connection') as probe:
            connection.request('POST', '/api/credential/check', '{}', headers)
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
            connection.close()
            probe.assert_not_called()
