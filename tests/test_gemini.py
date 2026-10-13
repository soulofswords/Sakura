import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
import app
import credentials
from llm import LLM

class GeminiTests(unittest.TestCase):
    def test_windows_key_protection(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(credentials, 'KEY_FILE', Path(folder)/'key.bin'):
            credentials.set_gemini_key('synthetic-key-for-tests')
            self.assertNotIn(b'synthetic-key-for-tests', credentials.KEY_FILE.read_bytes())
            self.assertEqual(credentials.get_gemini_key(), 'synthetic-key-for-tests')
            credentials.set_gemini_key('')
            self.assertEqual(credentials.get_gemini_key(), '')

    def test_settings_redact_key_preserve_it_and_switch(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app,'SETTINGS_FILE',Path(folder)/'settings.json'), patch.object(credentials,'KEY_FILE',Path(folder)/'key.bin'):
            llm=LLM(Path(folder)/'memory.json')
            with patch.object(app,'llm',llm),patch.object(app,'tts',None), patch.object(llm, 'configure_local'):
                client=TestClient(app.app)
                response=client.post('/api/settings',json={'llm_provider':'gemini','gemini_model':'gemini-flash-latest','gemini_api_key':'synthetic-key-for-tests'})
                self.assertEqual(response.status_code,200)
                self.assertTrue(response.json()['settings']['gemini_key_set'])
                self.assertNotIn('synthetic-key',response.text)
                self.assertNotIn('synthetic-key',app.SETTINGS_FILE.read_text())
                self.assertNotIn('synthetic-key',client.get('/api/settings').text)
                self.assertEqual(llm.provider,'gemini')
                self.assertTrue(app.get_vision_status()['ready'])
                self.assertEqual(client.post('/api/settings',json={'llm_provider':'ollama'}).status_code, 200)
                self.assertEqual(llm.provider,'ollama')
                self.assertEqual(credentials.get_gemini_key(),'synthetic-key-for-tests')
                client.post('/api/settings',json={'clear_gemini_key':True})
                self.assertEqual(llm.gemini_api_key,'')
                self.assertEqual(client.post('/api/settings',json={'gemini_model':'../../bad'}).status_code,400)

    def test_text_images_and_memory_use_correct_request(self):
        with tempfile.TemporaryDirectory() as folder:
            llm=LLM(Path(folder)/'memory.json')
            llm.configure_provider('gemini','gemini-flash-latest','synthetic-key')
            response=Mock(ok=True)
            response.json.return_value={'candidates':[{'content':{'parts':[{'text':'internal','thought':True},{'text':'I see your screen.'}]}}]}
            with patch('llm.requests.post',return_value=response) as post:
                self.assertEqual(llm.chat('What do you see?', '/9j/'),'I see your screen.')
                args=post.call_args
                self.assertNotIn('synthetic-key',args.args[0])
                self.assertEqual(args.kwargs['headers']['x-goog-api-key'],'synthetic-key')
                payload=args.kwargs['json']
                self.assertEqual(payload['contents'][-1]['parts'][1]['inlineData']['mimeType'],'image/jpeg')
                self.assertIn('systemInstruction',payload)
            self.assertNotIn('/9j/',llm.memory_path.read_text())
            history=list(llm.history)
            llm.configure_provider('ollama','gemini-flash-latest','synthetic-key')
            self.assertEqual(llm.history,history)

    def test_http_error_never_echoes_key(self):
        with tempfile.TemporaryDirectory() as folder:
            llm=LLM(Path(folder)/'memory.json');llm.configure_provider('gemini',api_key='synthetic-key')
            response=Mock(ok=False,status_code=403)
            with patch('llm.requests.post',return_value=response):
                reply=llm.chat('hello')
                self.assertIn('403',reply)
                self.assertNotIn('synthetic-key',reply)
                self.assertEqual(llm.history,[])

    def test_missing_key_does_not_fall_back_to_ollama(self):
        with tempfile.TemporaryDirectory() as folder:
            llm=LLM(Path(folder)/'memory.json');llm.configure_provider('gemini')
            with patch('llm.requests.post') as post:
                self.assertIn('API key is missing',llm.chat('hello'))
                post.assert_not_called()

    def test_connection_error_reports_reason_without_key(self):
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder)/'memory.json')
            llm.configure_provider('gemini', api_key='synthetic-key')
            with patch.object(app, 'llm', llm), patch.object(llm, 'test_gemini_connection', side_effect=ValueError('HTTP 403: synthetic-key rejected')):
                response = TestClient(app.app).post('/api/llm/test')
                self.assertEqual(response.status_code, 400)
                self.assertIn('403', response.text)
                self.assertNotIn('synthetic-key', response.text)

    def test_overload_retries_then_succeeds(self):
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder)/'memory.json')
            llm.configure_provider('gemini', api_key='synthetic-key')
            busy = Mock(ok=False, status_code=503, headers={})
            success = Mock(ok=True)
            success.json.return_value = {'candidates':[{'content':{'parts':[{'text':'Hello'}]}}]}
            with patch('llm.requests.post', side_effect=[busy, busy, success]) as post, patch('llm.time.sleep') as sleep:
                self.assertEqual(llm.chat('hello'), 'Hello')
                self.assertEqual(post.call_count, 3)
                self.assertEqual([call.args[0] for call in sleep.call_args_list], [2, 4])
                self.assertEqual(len(llm.history), 2)

    def test_persistent_overload_has_clear_error_and_no_fake_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder)/'memory.json')
            llm.configure_provider('gemini', api_key='synthetic-key')
            with patch('llm.requests.post', return_value=Mock(ok=False, status_code=503, headers={'Retry-After':'100'})) as post, patch('llm.time.sleep') as sleep:
                reply = llm.chat('hello')
                self.assertIn('temporarily busy', reply)
                self.assertNotIn('Check your key', reply)
                self.assertEqual(post.call_count, 3)
                self.assertEqual([call.args[0] for call in sleep.call_args_list], [10, 10])
                self.assertEqual(llm.history, [])

    def test_invalid_key_is_not_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder)/'memory.json')
            llm.configure_provider('gemini', api_key='synthetic-key')
            with patch('llm.requests.post', return_value=Mock(ok=False, status_code=403)) as post, patch('llm.time.sleep') as sleep:
                self.assertIn('403', llm.chat('hello'))
                post.assert_called_once()
                sleep.assert_not_called()

if __name__=='__main__': unittest.main()
