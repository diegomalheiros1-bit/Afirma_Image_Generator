"""Desktop lifecycle contracts, without Windows UI, credentials or API calls."""
import logging
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

from support import IsolatedTest
from src.desktop_app import DesktopApp, MIN_SIZE, initial_size, on_ui_thread, run_desktop


class Event:
    def __init__(self):
        self.callbacks = []

    def __iadd__(self, callback):
        self.callbacks.append(callback)
        return self


class DesktopTests(IsolatedTest):
    def setUp(self):
        super().setUp()
        self.session = SimpleNamespace(lock=threading.RLock(), active=False, worker=None, command=Mock())
        self.webview = SimpleNamespace(FileDialog=SimpleNamespace(OPEN=10, FOLDER=20))
        self.app = DesktopApp(self.session, self.webview)
        self.app.window = Mock()
        self.app.window.native = None
        home = patch('src.desktop_app.Path.home', return_value=Path('test-home'))
        home.start()
        self.addCleanup(home.stop)

    def test_initial_size_fits_screen_and_keeps_minimum(self):
        self.assertEqual(initial_size([]), (1200, 800))
        self.assertEqual(initial_size([SimpleNamespace(width=1920, height=1080)]), (1360, 900))
        self.assertEqual(initial_size([SimpleNamespace(width=1024, height=768)]), (944, 678))
        self.assertEqual(initial_size([SimpleNamespace(width=400, height=300)]), MIN_SIZE)

    def test_owned_file_dialog_filters_multi_selection_and_cancel(self):
        self.app.window.create_file_dialog.return_value = (r'C:\Fotos\a.png', r'C:\Fotos\b.jpg')
        self.assertEqual(len(self.app.pick_files('photos')), 2)
        options = self.app.window.create_file_dialog.call_args.kwargs
        self.assertTrue(options['allow_multiple'])
        self.assertEqual(options['dialog_type'], 10)
        self.assertIn('*.webp', options['file_types'][0])
        self.app.window.create_file_dialog.return_value = None
        self.assertEqual(self.app.pick_files('queue'), [])
        self.assertEqual(self.app.window.create_file_dialog.call_args.kwargs['file_types'], ('Planilhas Excel (*.xlsx)',))
        self.app.pick_files('folder')
        self.assertEqual(self.app.window.create_file_dialog.call_args.kwargs['dialog_type'], 20)
        with self.assertRaises(ValueError):
            self.app.pick_files('unknown')

    def test_file_dialog_marshals_to_windows_ui_thread(self):
        calls = []
        native = SimpleNamespace(InvokeRequired=True, Invoke=lambda callback: (calls.append('invoked'), callback()))
        with patch.dict(sys.modules, {'System': SimpleNamespace(Action=lambda cb: cb)}):
            self.assertEqual(on_ui_thread(SimpleNamespace(native=native), lambda: ['selected']), ['selected'])
        self.assertEqual(calls, ['invoked'])

    def test_idle_window_closes_without_prompt(self):
        self.assertTrue(self.app.on_closing())
        self.app.window.create_confirmation_dialog.assert_not_called()
        self.session.command.assert_not_called()

    def test_cancel_close_preserves_active_campaign(self):
        self.session.active = True
        self.app.window.create_confirmation_dialog.return_value = False
        self.assertFalse(self.app.on_closing())
        self.assertFalse(self.app.close_pending)
        self.session.command.assert_not_called()
        self.app.window.destroy.assert_not_called()

    def test_accept_close_waits_for_current_worker_and_ignores_duplicate(self):
        finished = threading.Event()
        destroyed = threading.Event()
        self.session.active = True
        self.session.worker = threading.Thread(target=finished.wait)
        self.session.worker.start()
        self.addCleanup(lambda: (finished.set(), self.session.worker.join(2)))
        self.app.window.create_confirmation_dialog.return_value = True
        self.app.window.destroy.side_effect = destroyed.set
        self.assertFalse(self.app.on_closing())
        self.assertFalse(self.app.on_closing())
        self.session.command.assert_called_once_with('stop')
        self.app.window.create_confirmation_dialog.assert_called_once()
        self.assertFalse(destroyed.wait(.02))
        finished.set()
        self.assertTrue(destroyed.wait(2))

    def test_campaign_finishing_during_prompt_closes_normally(self):
        self.session.active = True
        def confirm(*args):
            self.session.active = False
            return True
        self.app.window.create_confirmation_dialog.side_effect = confirm
        self.assertTrue(self.app.on_closing())
        self.session.command.assert_not_called()

    def run_shell(self, renderer='edgechromium'):
        stopped = threading.Event()
        server = Mock(server_port=12345)
        server.serve_forever.side_effect = stopped.wait
        server.shutdown.side_effect = stopped.set
        window = SimpleNamespace(events=SimpleNamespace(closing=Event(), loaded=Event(), initialized=Event()))
        view = SimpleNamespace(settings={}, screens=[], create_window=Mock(return_value=window), start=Mock())
        def start(**kwargs):
            window.events.initialized.callbacks[0](renderer)
            for callback in window.events.loaded.callbacks:
                callback()
        view.start.side_effect = start
        ready = Mock()
        with patch('studio.make_server', return_value=server) as make, patch('webbrowser.open') as browser:
            try:
                run_desktop(self.session, data_dir=Path('data'), webview_module=view, on_ready=ready)
            finally:
                server.shutdown.assert_called_once()
                server.server_close.assert_called_once()
                browser.assert_not_called()
        return view, ready, make

    def test_shell_uses_resizable_native_webview2_and_cleans_server(self):
        view, ready, make = self.run_shell()
        options = view.create_window.call_args.kwargs
        self.assertTrue(options['resizable'])
        self.assertFalse(options['frameless'])
        self.assertEqual(options['min_size'], (520, 500))
        self.assertEqual(options['url'], 'http://127.0.0.1:12345/')
        self.assertEqual(view.start.call_args.kwargs['gui'], 'edgechromium')
        self.assertFalse(view.start.call_args.kwargs['debug'])
        self.assertTrue(view.start.call_args.kwargs['private_mode'])
        self.assertFalse(view.settings['ALLOW_FILE_URLS'])
        self.assertTrue(view.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'])
        self.assertEqual(self.session.app_mode, 'desktop')
        self.assertIsNone(make.call_args.kwargs.get('host'))  # Default is loopback.
        ready.assert_called_once()

    def test_unsupported_renderer_fails_and_still_closes_server(self):
        with self.assertRaisesRegex(RuntimeError, 'WebView2'):
            self.run_shell('mshtml')

    def test_windowed_logger_works_without_stderr(self):
        from src.logger import get_logger
        old = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary:
            import os
            os.chdir(temporary)
            try:
                isolated = logging.Logger('desktop-test')
                with patch('src.logger.logging.getLogger', return_value=isolated), patch('src.logger.sys.stderr', None):
                    logger = get_logger()
                    logger.info('Desktop log available')
                    self.assertEqual(len(logger.handlers), 1)
                    self.assertIsInstance(logger.handlers[0], logging.FileHandler)
                    logger.handlers[0].close()
                    self.assertIn('Desktop log available', Path('logs/processamento.log').read_text('utf-8'))
            finally:
                os.chdir(old)
