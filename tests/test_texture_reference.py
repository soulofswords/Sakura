import json
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from app import app

class TextureReferenceTests(unittest.TestCase):
    def test_missing_texture_requires_reference_comparison(self):
        client = TestClient(app)
        response = client.post('/api/models/texture-check', json={'paths': ['pmx/not-present/absent.png']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['missing'], ['pmx/not-present/absent.png'])
        self.assertIn('PMX Editor', response.json()['reference'])

    def test_invalid_input(self):
        client = TestClient(app)
        self.assertEqual(client.post('/api/models/texture-check', json={'paths': 'file.png'}).status_code, 400)

    def test_optional_sphere_map_does_not_require_editor(self):
        client = TestClient(app)
        path = 'pmx/not-present/shine.bmp'
        result = client.post('/api/models/texture-check', json={'paths': [path], 'optional_paths': [path]}).json()
        self.assertEqual(result['required_missing'], [])
        self.assertEqual(result['optional_missing'], [path])
        self.assertEqual(result['reference'], '')

    def test_optional_paths_must_be_checked(self):
        client = TestClient(app)
        self.assertEqual(client.post('/api/models/texture-check', json={'paths': [], 'optional_paths': ['other.png']}).status_code, 400)

    def test_haku_texture_references(self):
        source = Path('audit-results/haku-2026-10-09/source.json')
        if not source.exists():
            self.skipTest('Haku audit source is absent')
        client = TestClient(app)
        report = []
        for item in json.loads(source.read_text(encoding='utf-8')):
            model = Path(item['file'])
            used = {m['texture'] for m in item['materials'] if m['texture'] >= 0}
            used |= {m['sphere'] for m in item['materials'] if m['sphereMode'] and m['sphere'] >= 0}
            paths = [(model.parent / item['textures'][i].replace('\\', '/')).relative_to('models').as_posix() for i in used]
            result = client.post('/api/models/texture-check', json={'paths': paths})
            self.assertEqual(result.status_code, 200)
            report.append({'model': model.as_posix(), **result.json(), 'badVertices': item.get('badVertices'), 'badFaces': item.get('badFaces')})
        Path('audit-results/haku-2026-10-09/textures.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
