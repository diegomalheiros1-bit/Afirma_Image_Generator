"""Mac contracts tested offline with mocked OS services, never a real keychain."""
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from support import IsolatedTest
from src.credential_store import CredentialStore, MacCredentialStore


class MacTests(IsolatedTest):
    def test_keychain_store_has_no_plaintext_file_and_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('src.credential_store.sys.platform', 'darwin'):
                store = CredentialStore(Path(directory) / 'settings.json')
            self.assertIsInstance(store, MacCredentialStore)
            backend = Mock()
            backend.get_password.return_value = None
            with patch.object(store, '_backend', return_value=backend):
                self.assertFalse(store.exists())
                store.save('fake-test-value')
                self.assertTrue(store.exists())
                backend.set_password.assert_called_once_with(store.service, store.account, 'fake-test-value')
                backend.get_password.return_value = 'fake-test-value'
                self.assertEqual(store.read(), 'fake-test-value')
                store.clear()
                backend.delete_password.assert_called_once_with(store.service, store.account)
                self.assertFalse(store.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_keychain_failure_never_falls_back_to_plaintext(self):
        store = MacCredentialStore('isolated-settings.json')
        with patch.object(store, '_backend', side_effect=RuntimeError('secret exception content')):
            for operation in [store.read, lambda: store.save('fake-value'), store.clear]:
                with self.assertRaises(OSError) as raised:
                    operation()
                self.assertNotIn('secret exception content', str(raised.exception))
            self.assertTrue(store.exists())  # Locked store does not break UI rendering.

    def test_keychain_identity_is_stable_and_isolates_settings(self):
        a = MacCredentialStore('a/settings.json')
        self.assertEqual(a.service, MacCredentialStore('a/settings.json').service)
        self.assertNotEqual(a.service, MacCredentialStore('b/settings.json').service)

    def test_macos_data_folder(self):
        from desktop import user_data_dir
        with patch('desktop.sys.platform', 'darwin'), patch('desktop.Path.home', return_value=Path('home')):
            self.assertEqual(user_data_dir(), Path('home/Library/Application Support/Afirma Image Studio'))

    def test_finder_receives_literal_path_without_shell(self):
        from src.studio_session import StudioSession
        with tempfile.TemporaryDirectory(prefix='mac folder ') as directory:
            session = StudioSession(Path(directory) / 'settings.json', env={})
            session.preferences['output_dir'] = directory
            with patch('src.studio_session.sys.platform', 'darwin'), patch('src.studio_session.subprocess.run') as run:
                session.open_output_folder()
            run.assert_called_once_with(['/usr/bin/open', str(Path(directory).resolve())], check=True, timeout=10)

    def test_bundle_rejects_campaign_data(self):
        from scripts.build_macos_package import assert_public_bundle
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'app.py').write_text('pass', encoding='utf-8')
            assert_public_bundle(root)
            (root / 'client.xlsx').write_bytes(b'private')
            with self.assertRaisesRegex(RuntimeError, 'privado'):
                assert_public_bundle(root)
