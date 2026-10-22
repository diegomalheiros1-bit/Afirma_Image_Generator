"""Exercise the actual local HTTP boundary, including asset isolation."""
import http.client
import json
import tempfile
import threading
from pathlib import Path

from src.studio_session import StudioSession
from studio import make_server, WEB_ASSETS
from support import IsolatedTest


class WebAssetTests(IsolatedTest):
    def setUp(self):
        super().setUp()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        session = StudioSession(Path(self.temp.name) / 'settings.json', env={})
        self.server = make_server(session)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, path, *, token=False, host=None, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['X-Afirma-Token'] = self.server.session_token
        if host:
            headers['Host'] = host
        connection.request('GET' if body is None else 'POST', path, body=body, headers=headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_browser_loads_separate_assets_without_exposing_session_token(self):
        status, _, html = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn(self.server.session_token.encode(), html)
        self.assertNotIn(b'data:image/png;base64', html)
        self.assertNotIn(b'id="validate"', html)
        for route, (_, mime) in WEB_ASSETS.items():
            with self.subTest(route=route):
                status, headers, body = self.request(route)
                self.assertEqual(status, 200)
                self.assertTrue(body)
                self.assertEqual(headers['Content-Type'], mime)
                self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
                self.assertNotIn(self.server.session_token.encode(), body)

    def test_assets_do_not_weaken_host_or_api_authentication(self):
        self.assertEqual(self.request('/assets/studio.js', host='attacker.example')[0], 403)
        self.assertEqual(self.request('/api/state')[0], 403)
        self.assertEqual(self.request('/api/state', token=True)[0], 200)
        for path in ('/assets/../.env', '/assets/%2e%2e/.env', '/assets/studio.js?secret=1', '/.env'):
            self.assertEqual(self.request(path, token=True)[0], 404)

    def test_non_object_request_is_actionable_client_error(self):
        for body in ('[]', 'null', '1', '"text"'):
            with self.subTest(body=body):
                status, _, response = self.request('/api/start', token=True, body=body)
                self.assertEqual(status, 400)
                self.assertIn('objeto JSON', json.loads(response)['error'])
