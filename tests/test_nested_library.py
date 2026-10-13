import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app

class NestedLibraryTests(unittest.TestCase):
    def test_nested_folders_validation_and_texture_isolation(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'MODELS_DIR', Path(folder)):
            root = Path(folder)
            own = root/'pmx'/'pmx'/'zenless zone zero'/'Evelyn'
            other = root/'pmx'/'pmx'/'zenless zone zero'/'Other'
            for package in (own, other):
                package.mkdir(parents=True)
                (package/'model.pmx').write_bytes(b'PMX '+bytes(5))
            (own/'broken.pmx').write_bytes(b'bad')
            junk=own/'__MACOSX';junk.mkdir();(junk/'._model.pmx').write_bytes(b'bad')
            (own/'skin.png').write_bytes(b'own-texture')
            (other/'other.png').write_bytes(b'other-texture')
            client=TestClient(app.app)
            models=client.get('/api/models').json()['models']
            self.assertEqual(len(models),3)
            self.assertEqual(models[0]['folders'], ['zenless zone zero','Evelyn'])
            self.assertTrue(next(m for m in models if m['filename']=='broken.pmx')['error'])
            prefix='/models/pmx/pmx/zenless zone zero/Evelyn/'
            self.assertEqual(client.get(prefix+'tex/skin.png').content,b'own-texture')
            self.assertNotEqual(client.get(prefix+'tex/other.png').content,b'other-texture')
            self.assertEqual(client.get(prefix+'tex/other.png').headers['content-type'],'image/png')
