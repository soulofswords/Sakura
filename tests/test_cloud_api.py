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

    def test_a_proxy_on_this_pc_may_use_plain_http_on_loopback_only(self):
        for url in ['http://127.0.0.1:31415/v1','http://localhost:31415/v1','http://[::1]:31415/v1']:
            self.assertEqual(validate('compatible','aion-2.0',url)[0],url.rstrip('/'))
        # A host that merely begins with the loopback literal is still off this machine.
        for url in ['http://127.0.0.1.evil.example/v1','http://127.0.0.1:31415/v1?key=secret','http://localhost@evil.example/v1']:
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

    def test_agent_planner_offers_only_cloud_providers_with_a_saved_key(self):
        settings={'llm_provider':'openrouter','cloud_model':'deepseek/deepseek-chat-v3','cloud_endpoint':'','cloud_vision':False,
                  'ollama_model':'qwen3:4b','ollama_models_folder':'','gemini_fallback_enabled':False,'ollama_context':4096,'local_timeout':20}
        with tempfile.TemporaryDirectory() as folder,patch.object(credentials,'CLOUD_KEY_FILE',Path(folder)/'keys.bin'):
            credentials.set_cloud_key('openrouter','sk-or-fake-private')
            credentials.set_cloud_key('anthropic','sk-ant-fake-private')
            credentials.set_cloud_key('compatible','sk-compat-fake','http://127.0.0.1:8000/v1')
            model=LLM(Path(folder)/'memory.json');model.model='qwen3:4b'
            with patch.object(app,'llm',model),patch.object(app,'get_settings',lambda:settings):
                listed=app._agent_provider_status()
                ids=[item['id'] for item in listed]
                self.assertIn('openrouter',ids);self.assertIn('anthropic',ids);self.assertNotIn('groq',ids)
                self.assertIn('deepseek/deepseek-chat-v3',{item['id']:item['label'] for item in listed}['openrouter'])
                planner=app._agent_model_for('openrouter')
                self.assertEqual((planner.provider,planner.cloud_model,planner.cloud_endpoint),
                                 ('openrouter','deepseek/deepseek-chat-v3','https://openrouter.ai/api/v1'))
                self.assertEqual(model.provider,'ollama')
                with patch('cloud_api.requests.post',return_value=Mock(ok=True,json=lambda:{'choices':[{'message':{'content':'{}'}}]})) as post:
                    planner._request_raw([{'role':'user','content':'{}'}],structured=True,planning=True)
                    self.assertEqual(post.call_args.args[0],'https://openrouter.ai/api/v1/chat/completions')
                with self.assertRaisesRegex(ValueError,'saved API key'):app._agent_model_for('groq')
                with patch.object(app,'get_settings',lambda:{**settings,'llm_provider':'compatible','cloud_endpoint':'http://127.0.0.1:8000/v1','cloud_model':'aion-2.0'}):
                    # A proxy on this PC is plain http on loopback, so it is a planner like any other.
                    self.assertIn('compatible',[item['id'] for item in app._agent_provider_status()])
                    planner=app._agent_model_for('compatible')
                    self.assertEqual((planner.provider,planner.cloud_model,planner.cloud_endpoint),('compatible','aion-2.0','http://127.0.0.1:8000/v1'))
                    with patch('cloud_api.requests.post',return_value=Mock(ok=True,json=lambda:{'choices':[{'message':{'content':'{}'}}]})) as post:
                        planner._request_raw([{'role':'user','content':'{}'}],structured=True,planning=True)
                        self.assertEqual(post.call_args.args[0],'http://127.0.0.1:8000/v1/chat/completions')
                with patch.object(app,'get_settings',lambda:{**settings,'llm_provider':'ollama','cloud_endpoint':'http://127.0.0.1:8000/v1','cloud_model':'aion-2.0'}):
                    # Chat went back to the local model, but the saved loopback proxy still plans,
                    # and it is labelled as a machine-local endpoint rather than a cloud service.
                    listed=app._agent_provider_status()
                    self.assertIn('compatible',[item['id'] for item in listed])
                    self.assertTrue({item['id']:item['label'] for item in listed}['compatible'].startswith('This PC · '))
                    planner=app._agent_model_for('compatible')
                    self.assertEqual((planner.provider,planner.cloud_model,planner.cloud_endpoint),('compatible','aion-2.0','http://127.0.0.1:8000/v1'))
                    self.assertEqual(model.provider,'ollama')
                    with patch('cloud_api.requests.post',return_value=Mock(ok=True,json=lambda:{'choices':[{'message':{'content':'{}'}}]})) as post:
                        planner._request_raw([{'role':'user','content':'{}'}],structured=True,planning=True)
                        self.assertEqual(post.call_args.args[0],'http://127.0.0.1:8000/v1/chat/completions')
                with patch.object(app,'get_settings',lambda:{**settings,'llm_provider':'ollama','cloud_endpoint':'https://remote.example/v1','cloud_model':'aion-2.0'}):
                    # A leftover remote custom endpoint must not start planning silently, even with a key.
                    credentials.set_cloud_key('compatible','sk-remote-fake','https://remote.example/v1')
                    self.assertNotIn('compatible',[item['id'] for item in app._agent_provider_status()])
                with patch.object(app,'get_settings',lambda:{**settings,'llm_provider':'ollama','cloud_endpoint':'http://[bad','cloud_model':'aion-2.0'}):
                    # The settings file is hand-editable; a malformed saved endpoint must leave the
                    # provider unoffered instead of breaking every read of the planner list.
                    self.assertNotIn('compatible',[item['id'] for item in app._agent_provider_status()])
                with patch.object(app,'get_settings',lambda:{**settings,'llm_provider':'compatible','cloud_endpoint':'http://example.com/v1'}):
                    self.assertNotIn('compatible',[item['id'] for item in app._agent_provider_status()])


if __name__=='__main__':unittest.main()
