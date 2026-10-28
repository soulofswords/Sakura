import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import credentials
import app
from cloud_api import detect_provider,request,validate
from llm import LLM


class CloudTests(unittest.TestCase):
    def test_detection_is_offline_and_ambiguous_keys_require_choice(self):
        with patch('cloud_api.requests.post') as post:
            for key,provider in [('AIzaExample','gemini'),('sk-proj-example','openai'),('sk-ant-example','anthropic'),('gsk_example','groq'),('sk-or-example','openrouter')]:
                self.assertEqual(detect_provider(key),provider)
            with self.assertRaisesRegex(ValueError,'ambiguous'):detect_provider('sk-ambiguous')
            post.assert_not_called()

    def test_openai_and_anthropic_requests_keep_images_and_separate_keys(self):
        messages=[{'role':'system','content':'Be concise.'},{'role':'user','content':'What is this?','images':['/9j/']}]
        response=Mock(ok=True);response.json.return_value={'choices':[{'message':{'content':'A phone.'}}]}
        with patch('cloud_api.requests.post',return_value=response) as post:
            self.assertEqual(request('openai','gpt-4.1-mini','test-key',messages,vision=True),'A phone.')
            self.assertEqual(post.call_args.args[0],'https://api.openai.com/v1/chat/completions')
            self.assertEqual(post.call_args.kwargs['headers'],{'Authorization':'Bearer test-key'})
            self.assertFalse(post.call_args.kwargs['allow_redirects'])
            self.assertIn('image_url',post.call_args.kwargs['json']['messages'][-1]['content'][1])
            response.json.return_value={'content':[{'type':'text','text':'Headphones.'}]}
            self.assertEqual(request('anthropic','claude-haiku-4-5','claude-test',messages,vision=True),'Headphones.')
            self.assertIn('api.anthropic.com',post.call_args.args[0])
            self.assertEqual(post.call_args.kwargs['headers']['x-api-key'],'claude-test')
            self.assertEqual(post.call_args.kwargs['json']['messages'][-1]['content'][1]['source']['type'],'base64')

    def test_http_errors_hide_provider_body_and_keys(self):
        with patch('cloud_api.requests.post',return_value=Mock(ok=False,status_code=401,text='secret-test-key')):
            with self.assertRaisesRegex(ValueError,'API key rejected') as caught:
                request('openai','gpt-4.1-mini','secret-test-key',[{'role':'user','content':'hello'}])
            self.assertNotIn('secret-test-key',str(caught.exception))
        with self.assertRaisesRegex(ValueError,'text only'):
            request('deepseek','deepseek-chat','key',[{'role':'user','content':'hello','images':['/9j/']}])
        for url in ['http://example.com/v1','https://user:password@example.com/v1','https://example.com/v1?key=secret']:
            with self.assertRaises(ValueError):validate('compatible','model',url)

    def test_key_storage_encrypted_and_custom_endpoint_bound(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(credentials,'CLOUD_KEY_FILE',Path(folder)/'keys.bin'):
            credentials.set_cloud_key('openai','private-test-key')
            self.assertNotIn(b'private-test-key',credentials.CLOUD_KEY_FILE.read_bytes())
            self.assertEqual(credentials.get_cloud_key('openai'),'private-test-key')
            self.assertEqual(credentials.get_cloud_key('anthropic'),'')
            credentials.set_cloud_key('compatible','custom-private','https://one.example/v1')
            self.assertEqual(credentials.get_cloud_key('compatible','https://two.example/v1'),'')

    def test_llm_cloud_chat_preserves_memory_and_never_uses_ollama(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json');model.configure_cloud('openai','','fake-key')
            with patch('cloud_api.requests.post') as post:
                post.return_value=Mock(ok=True);post.return_value.json.return_value={'choices':[{'message':{'content':'Hello!'}}]}
                self.assertEqual(model.chat('hello'),'Hello!')
                self.assertEqual(model.history,[])
                post.assert_not_called()

    def test_settings_detect_route_save_and_redact(self):
        from local_client import TestClient
        with tempfile.TemporaryDirectory() as folder,patch.object(app,'SETTINGS_FILE',Path(folder)/'settings.json'),patch.object(credentials,'CLOUD_KEY_FILE',Path(folder)/'keys.bin'),patch.object(credentials,'KEY_FILE',Path(folder)/'gemini.bin'):
            model=LLM(Path(folder)/'memory.json')
            with patch.object(app,'llm',model),patch.object(app,'tts',None):
                client=TestClient(app.app)
                response=client.post('/api/settings',json={'llm_provider':'auto','api_key':'sk-proj-fake-private'})
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(response.json()['settings']['llm_provider'],'openai')
                self.assertTrue(response.json()['settings']['cloud_key_set'])
                self.assertNotIn('sk-proj-fake-private',response.text)
                self.assertNotIn('sk-proj-fake-private',app.SETTINGS_FILE.read_text())
                self.assertEqual(model.provider,'openai')
                self.assertEqual(client.post('/api/settings',json={'llm_provider':'auto','api_key':'sk-unknown'}).status_code,400)
                self.assertEqual(client.post('/api/settings',json={'llm_provider':'anthropic'}).status_code,400)


if __name__=='__main__':unittest.main()
