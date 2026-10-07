import http.client
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from studio import make_server


class WifiTests(unittest.TestCase):
    def test_reject_public_wildcard_and_paid_api(self):
        for host in ('0.0.0.0', '8.8.8.8', '::1'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                make_server(SimpleNamespace(allow_api=False), host=host)
        with self.assertRaises(ValueError):
            make_server(SimpleNamespace(allow_api=True), host='192.168.1.2')

    def test_lan_link_cookie_host_origin_and_api_token(self):
        # Exercise LAN policy using only a loopback listener in the test environment.
        with patch('studio.ThreadingHTTPServer', side_effect=lambda address, handler:
                   ThreadingHTTPServer(('127.0.0.1', 0), handler)):
            server = make_server(SimpleNamespace(allow_api=False, state=lambda: {'allow_api':False}), host='192.168.1.2')
        thread=threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(path='/', **headers):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
            try:
                connection.request('GET',path,headers={'Host':f'192.168.1.2:{server.server_port}',**headers})
                response=connection.getresponse()
                return response.status,dict(response.getheaders()),response.read()
            finally:
                connection.close()
        try:
            self.assertEqual(request()[0],403)
            self.assertEqual(request('/?access=wrong')[0],403)
            link='/?access='+server.access_key
            self.assertEqual(request(link,Origin='http://untrusted.example')[0],403)
            status,headers,_=request(link)
            self.assertEqual(status,303)
            self.assertEqual(headers['Location'],'/')
            self.assertIn('HttpOnly',headers['Set-Cookie'])
            self.assertIn('SameSite=Strict',headers['Set-Cookie'])
            cookie=headers['Set-Cookie'].split(';')[0]
            self.assertEqual(request(Cookie=cookie)[0],200)
            self.assertEqual(request(Cookie=cookie,Host='untrusted.example')[0],403)
            self.assertEqual(request('/api/state',Cookie=cookie)[0],403)
            self.assertEqual(request('/api/state',**{'X-Afirma-Token':server.session_token})[0],403)
            self.assertEqual(request('/api/state',Cookie=cookie,**{'X-Afirma-Token':server.session_token})[0],200)
        finally:
            server.shutdown();server.server_close();thread.join()
