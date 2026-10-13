import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
import app
from llm import LLM

class TrackingModeTests(unittest.TestCase):
    def test_gemini_only_switch_never_contacts_ollama(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json');model.provider='gemini'
            with patch.object(app,'llm',model),patch.object(app,'stt_task',None),patch.object(app,'save_settings'),patch('rvc_manager.stop_rvc_service'),patch('youtube_chat.chat.stop'),patch('requests.get',side_effect=AssertionError('Unexpected Ollama call')):
                result=TestClient(app.app).post('/api/tracking/mode',json={'enabled':True})
                self.assertEqual(result.status_code,200,result.text)
                self.assertTrue(app.app.state.ai_unloaded)
    def setUp(self):
        self.previous_tts=app.tts
        app.tts=None
        app.app.state.tracking_only = False
        app.app.state.ai_unloaded = False
        app.app.state.llm_warmup = None
    def tearDown(self):
        app.tts=self.previous_tts
        app.app.state.tracking_only = False
        app.app.state.ai_unloaded = False
    def test_tracking_unloads_local_models_and_blocks_chat_speech(self):
        with tempfile.TemporaryDirectory() as folder:
            llm=LLM(Path(folder)/'memory.json')
            llm.vision_model='qwen3-vl:2b-instruct'
            response=Mock(status_code=200)
            with patch.object(app,'llm',llm),patch.object(app,'stt',object()),patch.object(app,'stt_task',None),patch.object(app,'save_settings'),patch('rvc_manager.stop_rvc_service') as stop,patch('youtube_chat.chat.stop'),patch('requests.get',return_value=response),patch('requests.post',return_value=response) as post:
                client=TestClient(app.app)
                result=client.post('/api/tracking/mode',json={'enabled':True})
                self.assertEqual(result.status_code,200,result.text)
                self.assertTrue(llm.tracking_only)
                self.assertIsNone(app.stt)
                self.assertEqual({c.kwargs['json']['model'] for c in post.call_args_list},{llm.model,llm.vision_model})
                self.assertTrue(all(c.kwargs['json']['keep_alive']==0 for c in post.call_args_list))
                stop.assert_called_once()
                for path in ['/api/chat','/api/stt','/api/tts/speak','/api/vtuber/connect']:
                    self.assertEqual(client.post(path,json={'text':'hello'}).status_code,409)
                client.post('/api/tracking/mode',json={'enabled':True})
                self.assertEqual(post.call_count,2,'Repeated start must not reload or unload again')
    def test_restore_ai_and_validate_mode_input(self):
        with tempfile.TemporaryDirectory() as folder:
            llm=LLM(Path(folder)/'memory.json')
            llm.tracking_only=True
            app.app.state.tracking_only=True
            with patch.object(app,'llm',llm),patch.object(app,'save_settings'),patch.object(llm,'configure_local') as configure,patch.object(llm,'warmup'),patch('rvc_manager.stop_rvc_service'):
                client=TestClient(app.app)
                self.assertEqual(client.post('/api/tracking/mode',json={'enabled':'yes'}).status_code,400)
                result=client.post('/api/tracking/mode',json={'enabled':False})
                self.assertEqual(result.status_code,200,result.text)
                self.assertFalse(llm.tracking_only)
                self.assertFalse(app.app.state.tracking_only)
                configure.assert_called_once()
    def test_failed_unload_does_not_claim_models_are_unloaded(self):
        with tempfile.TemporaryDirectory() as folder:
            llm=LLM(Path(folder)/'memory.json')
            with patch.object(app,'llm',llm),patch.object(app,'stt_task',None),patch('rvc_manager.stop_rvc_service'),patch('youtube_chat.chat.stop'),patch('requests.get',return_value=Mock(status_code=200)),patch('requests.post',side_effect=RuntimeError('unavailable')):
                result=TestClient(app.app).post('/api/tracking/mode',json={'enabled':True})
                self.assertEqual(result.status_code,503)
                self.assertTrue(app.app.state.tracking_only)
                self.assertFalse(app.app.state.ai_unloaded)

    def test_missing_runtime_does_not_block_tracking(self):
        import requests, errno
        with tempfile.TemporaryDirectory() as folder:
            llm=LLM(Path(folder)/'memory.json'); llm.provider='gemini'
            error=requests.ConnectionError('runtime absent')
            error.__cause__=ConnectionRefusedError(errno.ECONNREFUSED, 'refused')
            with patch.object(app,'llm',llm),patch.object(app,'stt_task',None),patch.object(app,'save_settings'),patch('rvc_manager.stop_rvc_service'),patch('youtube_chat.chat.stop'),patch('requests.get',side_effect=error),patch('requests.post') as post:
                response=TestClient(app.app).post('/api/tracking/mode',json={'enabled':True})
                self.assertEqual(response.status_code,200,response.text)
                self.assertTrue(app.app.state.ai_unloaded)
                post.assert_not_called()

    def test_runtime_timeout_does_not_claim_unloaded(self):
        import requests
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(app,'llm',LLM(Path(folder)/'memory.json')),patch.object(app,'stt_task',None),patch('rvc_manager.stop_rvc_service'),patch('youtube_chat.chat.stop'),patch('requests.get',side_effect=requests.Timeout('busy')):
                self.assertEqual(TestClient(app.app).post('/api/tracking/mode',json={'enabled':True}).status_code,503)
                self.assertFalse(app.app.state.ai_unloaded)

    def test_chat_reader_uses_selected_builtin_voice_without_llm(self):
        from unittest.mock import AsyncMock
        app.app.state.tracking_only=True
        voice=Mock();voice.speak_to_file_async=AsyncMock(return_value='chat.mp3')
        with patch('tts.TextToSpeech',return_value=voice),patch.object(app,'get_settings',return_value={'selected_voice':'guy_english'}),patch.object(app,'llm') as llm,patch('youtube_chat.chat.connect',return_value='abcdefghijk'):
            client=TestClient(app.app)
            self.assertEqual(client.post('/api/vtuber/connect',json={'link':'abcdefghijk'}).status_code,409)
            self.assertEqual(client.post('/api/chat-reader/connect',json={'link':'abcdefghijk'}).status_code,200)
            response=client.post('/api/chat-reader/speak',json={'text':'Viewer says hello'})
            self.assertEqual(response.status_code,200,response.text)
            voice.set_voice_preset.assert_called_once_with('guy_english')
            llm._request.assert_not_called()

    def test_chat_reader_keeps_selected_rvc_snapshot(self):
        from unittest.mock import AsyncMock
        app.app.state.tracking_only=True
        voice=Mock();voice.selected_preset_id='rvc_custom';voice.rvc_model='voice.pth';voice.speak_to_file_async=AsyncMock(return_value='converted.wav')
        with patch.object(app,'tts',voice),patch.object(app,'llm') as llm:
            response=TestClient(app.app).post('/api/chat-reader/speak',json={'text':'Viewer says hello'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['audio'],'/audio/converted.wav')
        voice.set_voice_preset.assert_not_called();voice.speak_to_file_async.assert_awaited_once_with('Viewer says hello');llm._request.assert_not_called()

if __name__=='__main__': unittest.main()
