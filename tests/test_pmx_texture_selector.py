import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app


class PmxTextureSelectorTests(unittest.TestCase):
    def test_save_restore_and_model_isolation(self):
        with tempfile.TemporaryDirectory() as directory, patch('app.MODELS_DIR', Path(directory)):
            folder = Path(directory) / 'pmx' / 'character'
            folder.mkdir(parents=True)
            model = folder / 'one.pmx'
            model.write_bytes(b'original model bytes')
            (folder / 'skin.png').write_bytes(b'texture')
            mapping = folder / 'textures.json'
            mapping.write_text(json.dumps({'textures': {'old.png': 'skin.png'}, 'materials': {'two.pmx': {'0': {'diffuse': 'skin.png'}}}}))
            client = TestClient(app)
            options = client.get('/api/models/texture-options', params={'model': 'pmx/character/one.pmx'})
            self.assertEqual(options.json()['textures'], ['skin.png'])
            payload = {'model': 'pmx/character/one.pmx', 'material': 1, 'slot': 'diffuse', 'texture': 'skin.png'}
            self.assertEqual(client.post('/api/models/texture-material', json=payload).status_code, 200)
            data = json.loads(mapping.read_text())
            self.assertEqual(data['materials']['one.pmx']['1']['diffuse'], 'skin.png')
            self.assertEqual(data['materials']['two.pmx']['0']['diffuse'], 'skin.png')
            self.assertEqual(data['textures']['old.png'], 'skin.png')
            self.assertEqual(model.read_bytes(), b'original model bytes')
            payload['texture'] = None
            self.assertEqual(client.post('/api/models/texture-material', json=payload).status_code, 200)
            self.assertNotIn('diffuse', json.loads(mapping.read_text())['materials']['one.pmx']['1'])
            payload['texture'] = '../../outside.png'
            self.assertEqual(client.post('/api/models/texture-material', json=payload).status_code, 400)
            payload['texture'] = 'missing.png'
            self.assertEqual(client.post('/api/models/texture-material', json=payload).status_code, 400)

    def test_reject_outside_or_non_pmx(self):
        client = TestClient(app)
        self.assertEqual(client.get('/api/models/texture-options', params={'model': '../outside.pmx'}).status_code, 400)

