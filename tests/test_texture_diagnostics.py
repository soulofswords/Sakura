import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from PIL import Image
from app import app


class TextureDiagnosticsTests(unittest.TestCase):
    def test_confirmed_repairs_missing_ambiguous_invalid_and_authored_alpha(self):
        with tempfile.TemporaryDirectory() as directory, patch('app.MODELS_DIR', Path(directory)):
            root = Path(directory) / 'pmx' / 'character'
            root.mkdir(parents=True)
            model = root / 'one.pmx'
            model.write_bytes(b'original model')
            (root / 'textures').mkdir()
            image = root / 'textures' / 'hair.png'
            Image.new('RGBA', (8, 8), (250, 180, 90, 128)).save(image)
            original = image.read_bytes()
            (root / 'bad.png').write_bytes(b'corrupt')
            Image.new('RGB', (4, 4)).save(root / 'skirt.png')
            Image.new('RGB', (4, 4)).save(root / 'skirt.jpg')
            for name in ['a', 'b']:
                (root / name).mkdir()
                Image.new('RGB', (4, 4)).save(root / name / 'face.png')
            mapping = root / 'textures.json'
            mapping.write_text(json.dumps({'textures': {'wrong.png': 'textures/hair.png'}, 'materials': {'other.pmx': {'0': {'diffuse': 'keep.png'}}}}))
            slots = [dict(material=i, slot='diffuse', reference=reference) for i, reference in enumerate(
                ['hair.png', 'wrong.png', 'missing.png', 'face.png', 'bad.png', 'textures/hair.png', 'skirt.bmp'])]
            client = TestClient(app)
            response = client.post('/api/models/texture-diagnose', json={'model': 'pmx/character/one.pmx', 'slots': slots})
            self.assertEqual(response.status_code, 200, response.text)
            results = response.json()['slots']
            self.assertEqual([r['status'] for r in results], ['repairable', 'repairable', 'missing', 'missing', 'invalid', 'ok', 'missing'])
            self.assertEqual(results[0]['resolved'], 'textures/hair.png')
            self.assertEqual(results[0]['width'], 8)
            self.assertEqual(image.read_bytes(), original, 'Diagnosis must preserve texture pixels and alpha')
            for result in results[:2]:
                saved = client.post('/api/models/texture-material', json={'model': 'pmx/character/one.pmx', 'material': result['material'], 'slot': result['slot'], 'texture': result['resolved']})
                self.assertEqual(saved.status_code, 200)
            self.assertEqual(json.loads(mapping.read_text())['materials']['other.pmx']['0']['diffuse'], 'keep.png')
            self.assertEqual(model.read_bytes(), b'original model')
            again = client.post('/api/models/texture-diagnose', json={'model': 'pmx/character/one.pmx', 'slots': [dict(material=0, slot='diffuse', reference=results[0]['resolved'])]})
            self.assertEqual(again.json()['slots'][0]['status'], 'ok', 'Saved references stay repaired on subsequent loads')

    def test_reject_invalid_slots_and_outside_package(self):
        with tempfile.TemporaryDirectory() as directory, patch('app.MODELS_DIR', Path(directory)):
            root = Path(directory) / 'pmx'
            root.mkdir()
            (root / 'one.pmx').write_bytes(b'model')
            client = TestClient(app)
            for slots in ['bad', [dict(material=True, slot='diffuse', reference='skin.png')],
                          [dict(material=0, slot='diffuse', reference='../outside.png')],
                          [dict(material=0, slot='unknown', reference='skin.png')]]:
                self.assertEqual(client.post('/api/models/texture-diagnose', json={'model': 'pmx/one.pmx', 'slots': slots}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
