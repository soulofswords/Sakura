import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app
from tts import TextToSpeech
class SelectionLifecycleTests(unittest.TestCase):
 def test_rvc_selection_starts_then_builtin_stops_worker(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(app,'SETTINGS_FILE',Path(folder)/'settings.json'),patch.object(app,'llm',None),patch.object(app,'tts',TextToSpeech()),patch('rvc_manager.ensure_rvc_service') as start,patch('rvc_manager.stop_rvc_service') as stop:
   client=TestClient(app.app)
   response=client.post('/api/settings',json={'selected_voice':'rvc_miku','rvc_model':'voices/miku/HatsuneMikucvlc1.5V1_170e_3910s.pth'})
   self.assertEqual(response.status_code,200,response.text);start.assert_called_once();stop.assert_not_called()
   response=client.post('/api/settings',json={'selected_voice':'sonia_maid'})
   self.assertEqual(response.status_code,200,response.text);stop.assert_called_once();self.assertIsNone(app.tts.rvc_model)
   self.assertEqual(response.json()['settings']['rvc_model'],'')
 def test_invalid_model_does_not_start_worker(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(app,'SETTINGS_FILE',Path(folder)/'settings.json'),patch.object(app,'llm',None),patch('rvc_manager.ensure_rvc_service') as start:
   self.assertEqual(TestClient(app.app).post('/api/settings',json={'selected_voice':'rvc_custom','rvc_model':'missing.pth'}).status_code,400);start.assert_not_called()
