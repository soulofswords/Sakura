import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import requests
from fastapi.testclient import TestClient
import app
from llm import LLM
from ollama_runtime import validate_folder, server_for_folder
import ollama_runtime

class LocalFallbackTests(unittest.TestCase):
    def test_local_images_never_fall_back_to_cloud(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json')
            model.configure_provider('ollama', api_key='synthetic-key')
            model.configure_local('qwen3-vl:2b-instruct',fallback=True)
            with patch('llm.requests.post',side_effect=requests.ConnectionError), patch.object(model,'_request_gemini') as cloud:
                with self.assertRaises(requests.ConnectionError):
                    model._request_raw([{'role':'user','content':'What is here?','images':['synthetic-image']}])
                cloud.assert_not_called()

    def test_timeout_falls_back_once_with_same_conversation(self):
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            llm.configure_provider('ollama', api_key='synthetic-key')
            llm.configure_local('llama3.2:3b', fallback=True, context=2048, timeout=8)
            llm.history = [{'role': 'user', 'content': 'My favourite colour is blue.'},
                           {'role': 'assistant', 'content': 'I will remember.'}]
            with patch('llm.requests.post', side_effect=requests.Timeout), patch.object(llm, '_request_gemini', return_value='Blue.') as fallback:
                self.assertEqual(llm.chat('What colour do I like?'), 'Blue.')
                fallback.assert_called_once()
                messages = fallback.call_args.args[0]
                self.assertIn(llm.history[0], messages)
                self.assertEqual(messages[-1]['content'], 'What colour do I like?')
                self.assertEqual(llm.last_backend, 'gemini-fallback')
                self.assertEqual(llm.history[-1]['content'], 'Blue.')

    def test_memory_failure_uses_fallback_and_local_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            llm.configure_provider('ollama', api_key='synthetic-key')
            llm.configure_local('llama3.2:3b', fallback=True, context=2048, timeout=8)
            failed = Mock()
            failed.raise_for_status.side_effect = requests.HTTPError('Insufficient memory')
            # A greeting must not be used here: safe_smalltalk answers "hello" before any
            # provider is contacted, which would hide the fallback path being tested.
            with patch('llm.requests.post', return_value=failed) as post, patch.object(llm, '_request_gemini', return_value='Out of memory, so I used the cloud.'):
                self.assertEqual(llm.chat('What colour do I like?'), 'Out of memory, so I used the cloud.')
                self.assertEqual(post.call_args.kwargs['json']['model'], 'llama3.2:3b')
                self.assertEqual(post.call_args.kwargs['json']['options']['num_ctx'], 2048)
                self.assertEqual(post.call_args.kwargs['timeout'], (3, 8))

    def test_no_cloud_request_when_disabled_or_missing_key(self):
        for enabled, key in ((False, 'synthetic-key'), (True, '')):
            with tempfile.TemporaryDirectory() as folder:
                llm = LLM(Path(folder) / 'memory.json')
                llm.configure_provider('ollama', api_key=key)
                llm.configure_local('llama3.2:3b', fallback=enabled)
                with patch('llm.requests.post', side_effect=requests.ConnectionError), patch.object(llm, '_request_gemini') as fallback:
                    reply=llm.chat('What colour do I like?')
                    fallback.assert_not_called()
                    self.assertIsInstance(reply, str)
                    self.assertTrue(reply.strip())

    def test_folder_must_be_an_ollama_store_and_default_does_not_launch(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                validate_folder(folder)
            (Path(folder) / 'blobs').mkdir()
            (Path(folder) / 'manifests').mkdir()
            self.assertEqual(validate_folder(folder), str(Path(folder).resolve()))
        with patch('ollama_runtime.subprocess.Popen') as launch:
            self.assertEqual(server_for_folder(''), llm_base_url())
            launch.assert_not_called()

    def test_save_local_options_and_reject_fallback_without_key(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'SETTINGS_FILE', Path(folder) / 'settings.json'), patch.object(app, 'tts', None), patch.object(app, 'get_gemini_key', return_value=''):
            llm = LLM(Path(folder) / 'memory.json')
            tags = Mock()
            tags.json.return_value = {'models': [{'name': 'llama3.2:3b'}]}
            with patch.object(app, 'llm', llm), patch('llm.requests.get', return_value=tags), patch('llm.requests.post'):
                client = TestClient(app.app)
                self.assertEqual(client.post('/api/settings', json={'gemini_fallback_enabled': True}).status_code, 400)
                response = client.post('/api/settings', json={'ollama_model': 'llama3.2:3b', 'ollama_context': 2048, 'local_timeout': 8})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(llm.model, 'llama3.2:3b')
                self.assertEqual(response.json()['settings']['ollama_context'], 2048)
                self.assertEqual(client.post('/api/settings', json={'ollama_context': 0}).status_code, 400)

    @patch('ollama_runtime.sys.platform', 'win32')
    def test_custom_folder_launches_private_server_without_changing_system_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'blobs').mkdir()
            (Path(folder) / 'manifests').mkdir()
            bundled = Path(folder) / 'ollama-runtime' / 'ollama.exe'
            bundled.parent.mkdir()
            bundled.touch()
            process = Mock()
            process.poll.return_value = None
            response = Mock()
            response.status_code = 200
            response.json.return_value = {'models': []}  # real Ollama /api/tags shape
            with patch.object(ollama_runtime, 'BASE_DIR', Path(folder)), patch.object(ollama_runtime, 'ProcessJob') as job, patch.object(ollama_runtime, '_job', None), patch.object(ollama_runtime, '_worker', None), patch.object(ollama_runtime, '_folder', None), patch.object(ollama_runtime, '_url', None), patch('ollama_runtime.shutil.which', return_value='ollama.exe'), patch('ollama_runtime.subprocess.Popen', return_value=process) as launch, patch('ollama_runtime.requests.get', return_value=response), patch('ollama_runtime.open', unittest.mock.mock_open()), patch('gpu_info.detect_gpu', return_value={'vendor': 'nvidia', 'names': ['NVIDIA GeForce RTX 3080']}):
                base = server_for_folder(folder)
                self.assertTrue(base.startswith('http://127.0.0.1:'))
                environment = launch.call_args.kwargs['env']
                self.assertEqual(environment['OLLAMA_MODELS'], str(Path(folder).resolve()))
                self.assertEqual(launch.call_args.args[0], [str(bundled), 'serve'])
                self.assertEqual(server_for_folder(folder), base)
                launch.assert_called_once()
                job.return_value.attach_and_resume.assert_called_once_with(process)
                ollama_runtime.stop()
                job.return_value.close.assert_called_once()

    def test_connection_check_checks_fallback_when_local_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            llm.configure_provider('ollama', api_key='synthetic-key')
            llm.configure_local('llama3.2:3b', fallback=True)
            with patch.object(app, 'llm', llm), patch.object(llm, 'is_available', return_value=False), patch.object(llm, 'test_gemini_connection', return_value='Connected') as check:
                response = TestClient(app.app).post('/api/llm/test')
                self.assertEqual(response.status_code, 200)
                self.assertIn('Gemini fallback is ready', response.json()['message'])
                check.assert_called_once()

def llm_base_url():
    from config import OLLAMA_BASE_URL
    return OLLAMA_BASE_URL
