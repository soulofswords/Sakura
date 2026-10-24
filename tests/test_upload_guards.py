import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import app
from fastapi.testclient import TestClient


class VoiceUploadTests(unittest.TestCase):
    """The uploader only ever writes inside voices/<character>/."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.voices = self.root / 'voices'
        self.voices.mkdir()
        self.client = TestClient(app.app)

    def tearDown(self):
        self.folder.cleanup()

    def send(self, pth_name, pth_blob=b'weights', character='mia', index_name=None, index_blob=b'index'):
        files = {'pth_file': (pth_name, pth_blob, 'application/octet-stream')}
        if index_name:
            files['index_file'] = (index_name, index_blob, 'application/octet-stream')
        with patch.object(app, 'VOICES_DIR', self.voices), patch.object(app, 'BASE_DIR', self.root), \
                patch.object(app, 'save_settings', lambda data: data), patch.object(app, 'tts', None), \
                patch.object(app, 'llm', None):
            return self.client.post('/api/voices/upload', data={'character_name': character}, files=files)

    def test_a_normal_pair_is_saved_under_the_character(self):
        response = self.send('mia.pth', index_name='mia.index')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(sorted(p.name for p in (self.voices / 'mia').iterdir()), ['mia.index', 'mia.pth'])

    def test_traversal_names_cannot_reach_outside_the_character_folder(self):
        for name in ['../evil.pth', '..\\..\\evil.pth', 'C:\\Windows\\evil.pth', 'a/b.pth', 'voice/../../evil.pth']:
            self.assertEqual(self.send(name).status_code, 200, name)
        escaped = [p for p in self.root.rglob('evil.pth') if p.parent != (self.voices / 'mia')]
        self.assertEqual(escaped, [], f'written outside the character folder: {escaped}')
        self.assertTrue((self.voices / 'mia' / 'evil.pth').is_file())
        self.assertFalse((self.root / 'evil.pth').exists())

    def test_renamed_executables_and_other_kinds_are_refused(self):
        for name in ['evil.zip', 'evil.pth.exe', 'noext', 'install.ps1', 'evil.py']:
            self.assertEqual(self.send(name).status_code, 400, name)
        self.assertEqual(list(self.root.rglob('*')), [self.voices])

    def test_an_oversized_model_is_refused_and_left_behind_nothing(self):
        response = self.send('big.pth', pth_blob=b'x' * (app.MAX_RVC_BYTES + 10))
        self.assertEqual(response.status_code, 400)
        self.assertIn('512 MB', response.json()['error'])
        self.assertEqual(list(self.root.rglob('big.pth')), [])

    def test_a_traversal_index_name_stays_inside_the_character_folder(self):
        self.send('ok.pth', index_name='..\\..\\bad.index')
        self.assertEqual([p.relative_to(self.root).as_posix() for p in self.root.rglob('bad.index')],
                         ['voices/mia/bad.index'])

    def test_character_names_are_restricted(self):
        for character in ['...', '..\\pwn', 'mia é', 'a' * 60]:
            self.assertEqual(self.send('x.pth', character=character).status_code, 400, character)
        self.assertIn(self.send('x.pth', character='').status_code, (400, 422))
        self.assertEqual(self.send('x.pth', character='Big Mia').status_code, 200)
        self.assertTrue((self.voices / 'big_mia' / 'x.pth').is_file())


class InstallerOriginTests(unittest.TestCase):
    def test_local_and_native_callers_are_allowed_others_are_not(self):
        def guard(origin=None, site=None):
            headers = {}
            if origin:
                headers['origin'] = origin
            if site:
                headers['sec-fetch-site'] = site
            return app._started_locally(Mock(headers=headers))
        self.assertTrue(guard('http://127.0.0.1:8000'))
        self.assertTrue(guard('http://localhost:8000'))
        self.assertTrue(guard('http://[::1]:8000'))
        self.assertTrue(guard())                      # the desktop window sends no Origin
        self.assertTrue(guard(site='same-origin'))
        self.assertFalse(guard('http://evil.example'))
        self.assertFalse(guard('https://accounts.google.com'))
        self.assertFalse(guard('null'))
        self.assertFalse(guard(site='cross-site'))

    def test_a_cross_origin_page_cannot_start_the_installer(self):
        installer = Mock()
        with patch('nvidia_ar_feature_installer.installer', installer):
            response = TestClient(app.app).post('/api/tracking/nvidia-sdk/install-features',
                                                json={'api_key': 'ngc-fake', 'folder': 'C:/SDK'},
                                                headers={'origin': 'http://evil.example',
                                                         'sec-fetch-site': 'cross-site'})
        self.assertEqual(response.status_code, 403)
        installer.start.assert_not_called()


class ModelManagerOriginTests(unittest.TestCase):
    """Uninstalling weights is destructive, so a visited page must not trigger it."""

    def posted(self, manager, origin=None):
        headers = {}
        if origin:
            headers.update({'origin': origin, 'sec-fetch-site': 'cross-site'})
        payload = {'model': 'gemma3:4b', 'confirm': 'gemma3:4b'}
        with patch('local_model_manager.manager', manager):
            return TestClient(app.app).post('/api/ollama/manager/delete', json=payload, headers=headers)

    def test_a_cross_site_page_cannot_uninstall_a_model(self):
        manager = Mock()
        response = self.posted(manager, 'http://evil.example')
        self.assertEqual(response.status_code, 403)
        manager.remove.assert_not_called()

    def test_the_local_panel_still_reaches_the_real_uninstall_check(self):
        manager = Mock()
        manager.remove.return_value = {'ok': True, 'message': 'Uninstalled gemma3:4b. Other models were kept.'}
        response = self.posted(manager)
        self.assertEqual(response.status_code, 200)
        manager.remove.assert_called_once()


class StateChangingRouteOriginTests(unittest.TestCase):
    """Uploading weights, rewriting settings and pairing a phone all mutate this PC."""

    cross_site = {'origin': 'http://evil.example', 'sec-fetch-site': 'cross-site'}

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.voices = self.root / 'voices'
        self.saved = Mock(side_effect=lambda data: dict(data))
        self.client = TestClient(app.app)

    def tearDown(self):
        self.folder.cleanup()

    def call(self, method, path, **call):
        with patch.object(app, 'VOICES_DIR', self.voices), patch.object(app, 'BASE_DIR', self.root), \
                patch.object(app, 'save_settings', self.saved), patch.object(app, 'tts', None), \
                patch.object(app, 'llm', None):
            return getattr(self.client, method)(path, **call)

    def test_a_visited_page_cannot_upload_a_voice_model(self):
        response = self.call('post', '/api/voices/upload',
                             data={'character_name': 'mia'},
                             files={'pth_file': ('evil.pth', b'weights', 'application/octet-stream')},
                             headers=self.cross_site)
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(list(self.root.rglob('*')), [], 'the refused upload still wrote to disk')
        self.saved.assert_not_called()

    def test_a_visited_page_cannot_rewrite_settings(self):
        response = self.call('post', '/api/settings', json={'assistant_name': 'Not Sakura'}, headers=self.cross_site)
        self.assertEqual(response.status_code, 403, response.text)
        self.saved.assert_not_called()

    def test_a_visited_page_cannot_pair_a_phone_or_read_the_link(self):
        link = Mock()
        link.info.return_value = {'enabled': True, 'addresses': ['192.168.1.9']}
        with patch('mobile_link.link', link):
            refused = self.call('post', '/api/mobile/link', json={'new': True}, headers=self.cross_site)
            leaked = self.call('get', '/api/mobile/link', headers=self.cross_site)
        self.assertEqual(refused.status_code, 403, refused.text)
        self.assertEqual(leaked.status_code, 403, leaked.text)
        link.new_pairing_code.assert_not_called()

    def test_a_visited_page_cannot_launch_the_steam_installer(self):
        opener = Mock(return_value=True)
        with patch('webbrowser.open', opener):
            response = self.call('post', '/api/tracking/nvidia-expressionapp/install',
                                 headers=self.cross_site)
        self.assertEqual(response.status_code, 403, response.text)
        opener.assert_not_called()

    def test_the_local_panel_still_reaches_every_one_of_them(self):
        # Pinned provider settings so the route cannot be failed by whatever AI the user has saved.
        settings = {**app.get_settings(), 'llm_provider': 'ollama', 'gemini_fallback_enabled': False}
        with patch.object(app, 'get_settings', lambda: settings):
            response = self.call('post', '/api/settings', json={'assistant_name': 'Sakura'})
        self.assertEqual(response.status_code, 200, response.text)
        self.saved.assert_called_once_with({'assistant_name': 'Sakura'})
        response = self.call('post', '/api/voices/upload', data={'character_name': 'mia'},
                             files={'pth_file': ('mia.pth', b'weights', 'application/octet-stream')})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue((self.voices / 'mia' / 'mia.pth').is_file())
        link = Mock()
        link.info.return_value = {'enabled': False}
        with patch('mobile_link.link', link):
            self.assertEqual(self.call('post', '/api/mobile/link', json={'enabled': False}).status_code, 200)
            self.assertEqual(self.call('get', '/api/mobile/link').status_code, 200)
        link.stop.assert_called_once()
        with patch('nvidia_expressionapp_tracker.detect_installed_folder', lambda: 'C:/Steam/DLC'):
            response = self.call('post', '/api/tracking/nvidia-expressionapp/install')
        if sys.platform == 'win32':
            self.assertEqual(response.status_code, 200, response.text)
        else:
            self.assertEqual(response.status_code, 400, response.text)


class SettingsWriteTests(unittest.TestCase):
    def test_an_interrupted_write_keeps_the_previous_settings(self):
        with tempfile.TemporaryDirectory() as name:
            settings = Path(name) / 'settings.json'
            settings.write_text(json.dumps({'assistant_name': 'Sakura', 'local_timeout': 20}), encoding='utf-8')
            with patch.object(app, 'SETTINGS_FILE', settings), patch('os.fsync', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    app.save_settings({'assistant_name': 'Changed'})
            self.assertEqual(json.loads(settings.read_text(encoding='utf-8'))['assistant_name'], 'Sakura')
            self.assertEqual(list(Path(name).glob('.settings-*')), [])


if __name__ == '__main__':
    unittest.main()
