import tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app
class LayoutTests(unittest.TestCase):
 def test_grouped_discovery_legacy_url_and_texture_fallback(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(app,'MODELS_DIR',Path(folder)):
   root=Path(folder)/'pmx'/'Test Miku';root.mkdir(parents=True)
   (root/'model.pmx').write_bytes(b'PMX '+bytes(5))
   (root/'skin.png').write_bytes(b'texture-test')
   client=TestClient(app.app)
   models=client.get('/api/models').json()
   self.assertIn('Test miku',str(models));self.assertIn('pmx/Test Miku/model.pmx',str(models))
   for path in ('pmx/Test Miku/model.pmx','Test Miku/model.pmx'):
    self.assertEqual(client.get('/models/'+path).content,b'PMX '+bytes(5))
   self.assertEqual(client.get('/models/pmx/Test Miku/tex/skin.png').content,b'texture-test')
   self.assertEqual(client.get('/models/Test Miku/tex/skin.png').content,b'texture-test')
