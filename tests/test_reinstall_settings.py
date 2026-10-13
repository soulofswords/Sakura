import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app


class ReinstallSettingsTests(unittest.TestCase):
    def test_default_save_and_boolean_validation(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'SETTINGS_FILE', Path(folder)/'settings.json'), patch.object(app, 'llm', None), patch.object(app, 'tts', None):
            client = TestClient(app.app)
            self.assertTrue(client.get('/api/settings').json()['preserve_configuration_on_reinstall'])
            response = client.post('/api/settings', json={'preserve_configuration_on_reinstall': False, 'physics_boost': 85, 'pmx_texture_reference': True})
            self.assertEqual(response.status_code, 200)
            self.assertFalse(app.get_settings()['preserve_configuration_on_reinstall'])
            self.assertEqual(app.get_settings()['physics_boost'], 85)
            self.assertTrue(app.get_settings()['pmx_texture_reference'])
            self.assertEqual(client.post('/api/settings', json={'preserve_configuration_on_reinstall': 'false'}).status_code, 400)
