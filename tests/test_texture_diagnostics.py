import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from local_client import TestClient
from PIL import Image
from app import app


class TextureDiagnosticsTests(unittest.TestCase):
    def test_does_not_substitute_a_different_extension_for_missing_shading(self):
        with tempfile.TemporaryDirectory() as directory, patch('app.MODELS_DIR', Path(directory)):
            root = Path(directory) / 'pmx' / 'character'
            root.mkdir(parents=True)
            (root / 'one.pmx').write_bytes(b'model')
            Image.new('RGB', (4, 4), (70, 130, 200)).save(root / 'toon.png')
            client = TestClient(app)
            slots = [dict(material=0, slot='toon', reference='toon.bmp')]
            result = client.post('/api/models/texture-diagnose', json={'model': 'pmx/character/one.pmx', 'slots': slots})
            self.assertEqual(result.json()['slots'][0]['status'], 'missing')
            response = client.get('/models/pmx/character/toon.bmp?strict_texture=true&fallback=white')
            self.assertEqual(response.headers.get('X-Sakura-Asset-Fallback'), 'missing')

    def test_shine_and_toon_recovery_preserves_diffuse_and_other_model_edits(self):
        with tempfile.TemporaryDirectory() as directory, patch('app.MODELS_DIR', Path(directory)):
            root = Path(directory) / 'pmx' / 'character'
            root.mkdir(parents=True)
            (root / 'one.pmx').write_bytes(b'unchanged model')
            (root / 'tex').mkdir()
            (root / 'originals').mkdir()
            for filename in ['shine.spa', 'shade.bmp']:
                (root / 'tex' / filename).write_bytes(bytes(32))
                Image.new('RGBA', (4, 4), (30, 60, 90, 255)).save(root / 'originals' / filename, format='PNG')
            mapping = root / 'textures.json'
            mapping.write_text(json.dumps({'materials': {'one.pmx': {'0': {'diffuse': 'keep.png'}}, 'other.pmx': {'0': {'sphere': 'keep.spa'}}}}))
            client = TestClient(app)
            slots = [dict(material=0, slot='sphere', reference='tex/shine.spa'), dict(material=0, slot='toon', reference='tex/shade.bmp')]
            response = client.post('/api/models/texture-diagnose', json={'model': 'pmx/character/one.pmx', 'slots': slots})
            self.assertEqual(response.status_code, 200, response.text)
            for row in response.json()['slots']:
                self.assertEqual(row['status'], 'repairable')
                saved = client.post('/api/models/texture-material', json={'model': 'pmx/character/one.pmx', 'material': row['material'], 'slot': row['slot'], 'texture': row['resolved']})
                self.assertEqual(saved.status_code, 200)
            data = json.loads(mapping.read_text())['materials']
            self.assertEqual(data['one.pmx']['0'], {'diffuse': 'keep.png', 'sphere': 'originals/shine.spa', 'toon': 'originals/shade.bmp'})
            self.assertEqual(data['other.pmx']['0']['sphere'], 'keep.spa')

    def test_corrupt_texture_recovers_only_unique_valid_same_package_copy(self):
        with tempfile.TemporaryDirectory() as directory, patch('app.MODELS_DIR', Path(directory)):
            root = Path(directory) / 'pmx' / 'character'
            root.mkdir(parents=True)
            (root / 'one.pmx').write_bytes(b'unchanged model')
            (root / 'tex').mkdir()
            (root / 'originals').mkdir()
            broken = root / 'tex' / 'hair.png'
            broken.write_bytes(bytes(100))
            source = root / 'originals' / 'hair.png'
            Image.new('RGBA', (4, 4), (220, 140, 70, 128)).save(source)
            original = source.read_bytes()
            client = TestClient(app)
            payload = {'model': 'pmx/character/one.pmx', 'slots': [dict(material=0, slot='diffuse', reference='tex/hair.png')]}
            response = client.post('/api/models/texture-diagnose', json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            row = response.json()['slots'][0]
            self.assertEqual(row['status'], 'repairable')
            self.assertEqual(row['resolved'], 'originals/hair.png')
            self.assertEqual(broken.read_bytes(), bytes(100), 'Diagnosis must not replace source artwork')
            self.assertEqual(source.read_bytes(), original)
            Image.new('RGBA', (4, 4), (20, 40, 70, 255)).save(root / 'hair.png')
            self.assertEqual(client.post('/api/models/texture-diagnose', json=payload).json()['slots'][0]['status'], 'invalid', 'Ambiguous copies require manual selection')

    def test_recovery_never_reads_a_copy_outside_the_model_package(self):
        from pmx_texture_repair import PackageTextures
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / 'model'
            package.mkdir()
            Image.new('RGB', (4, 4)).save(root / 'hair.png')
            try:
                (package / 'hair.png').symlink_to(root / 'hair.png')
            except OSError:
                self.skipTest('Symlink creation is unavailable')
            self.assertIsNone(PackageTextures(package / 'one.pmx').recover('tex/hair.png'))

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
