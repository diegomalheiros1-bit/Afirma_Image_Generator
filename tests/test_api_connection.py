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
                self.assertEqual(result['status'], 'disconnected')
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

    def test_http_save_starts_probe_and_explicit_check_requires_local_auth(self):
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
            self.session.connection_worker.join(3)
            self.assertEqual(self.session.state()['api_connection']['status'], 'connected')
            self.assertEqual(request('/api/credential/check', {})[0], 200)
            self.session.connection_worker.join(3)
            self.assertEqual(probe.call_count, 2)

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
