import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from local_client import TestClient
import app as server


class CollabModelPackageTests(unittest.TestCase):
    def setUp(self):
        self.original_models = server.MODELS_DIR
        self.temp = tempfile.TemporaryDirectory(prefix='sakura-collab-test-')
        server.MODELS_DIR = Path(self.temp.name) / 'models'
        model_dir = server.MODELS_DIR / 'vrm' / 'sample'
        model_dir.mkdir(parents=True)
        (model_dir / 'アバター.vrm').write_bytes(b'fake vrm model')
        (model_dir / 'texture.png').write_bytes(b'fake texture')
        self.client = TestClient(server.app)

    def tearDown(self):
        server.MODELS_DIR = self.original_models
        self.temp.cleanup()

    def test_package_import_serve_and_remove(self):
        package = self.client.post('/api/collab/package', json={'path': 'vrm/sample/%E3%82%A2%E3%83%90%E3%82%BF%E3%83%BC.vrm'})
        self.assertEqual(package.status_code, 200)
        entry = package.headers['x-sakura-collab-entry']
        with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
            self.assertIn('アバター.vrm', archive.namelist())
            self.assertIn('texture.png', archive.namelist())

        imported = self.client.post('/api/collab/import', content=package.content,
                                    headers={'Content-Type': 'application/zip', 'X-Sakura-Collab-Entry': entry})
        self.assertEqual(imported.status_code, 200, imported.text)
        model_url = imported.json()['model_url']
        self.assertEqual(self.client.get(model_url).content, b'fake vrm model')
        token = model_url.split('/')[2]
        self.assertEqual(self.client.delete('/api/collab/import/' + token).status_code, 200)
        self.assertEqual(self.client.get(model_url).status_code, 404)

    def test_import_rejects_zip_path_traversal(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('../outside.vrm', b'bad')
            archive.writestr('avatar.vrm', b'entry')
        response = self.client.post('/api/collab/import', content=buffer.getvalue(),
                                    headers={'Content-Type': 'application/zip', 'X-Sakura-Collab-Entry': 'avatar.vrm'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse((Path(self.temp.name) / 'outside.vrm').exists())


if __name__ == '__main__':
    unittest.main()
