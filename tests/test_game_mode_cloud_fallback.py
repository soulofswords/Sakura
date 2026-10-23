import asyncio
import threading
import unittest
from unittest.mock import Mock, patch

import app


class FakeLLM:
    def __init__(self):
        self.provider = 'ollama'
        self.calls = []
        self._lock = threading.RLock()
        self.base_url = 'http://ollama.test'
        self.model = 'local-model'
        self.vision_model = 'local-vision'

    def configure_provider(self, provider, model, key):
        self.calls.append(('cloud', provider, model, key))
        self.provider = provider

    def configure_cloud(self, provider, model, key, endpoint, vision):
        self.calls.append(('cloud', provider, model, key))
        self.provider = provider

    def configure_local(self, model, folder, fallback, context, timeout, validate=False):
        self.calls.append(('local', model))
        self.provider = 'ollama'


class GameModeFallbackTests(unittest.TestCase):
    def test_saved_cloud_key_is_used_temporarily_then_local_is_restored(self):
        cfg = {'llm_provider': 'ollama', 'last_cloud_provider': 'gemini', 'gemini_model': 'gemini-flash-latest',
               'ollama_model': 'qwen3-vl:4b-instruct', 'ollama_models_folder': '',
               'gemini_fallback_enabled': False, 'ollama_context': 4096, 'local_timeout': 20}
        model = FakeLLM()
        with patch.object(app, 'llm', model), patch.object(app, 'get_settings', return_value=cfg), \
             patch.object(app, 'get_gemini_key', return_value='saved-test-key'), \
             patch('requests.get', return_value=Mock(raise_for_status=Mock())), \
             patch('requests.post', return_value=Mock(status_code=200, raise_for_status=Mock())) as unload:
            enabled = asyncio.run(app.game_mode_cloud_fallback({'active': True}))
            self.assertEqual(enabled, {'ok': True, 'active': True, 'provider': 'gemini'})
            self.assertEqual(model.provider, 'gemini')
            self.assertEqual(model.calls[-1], ('cloud', 'gemini', 'gemini-flash-latest', 'saved-test-key'))
            self.assertEqual(unload.call_count, 2)
            self.assertTrue(all(call.kwargs['json']['keep_alive'] == 0 for call in unload.call_args_list))
            disabled = asyncio.run(app.game_mode_cloud_fallback({'active': False}))
            self.assertEqual(disabled['provider'], 'ollama')
            self.assertEqual(model.provider, 'ollama')
            self.assertEqual(model.calls[-1], ('local', 'qwen3-vl:4b-instruct'))

    def test_missing_key_keeps_local_and_invalid_flag_is_rejected(self):
        cfg = {'llm_provider': 'ollama', 'last_cloud_provider': 'gemini'}
        model = FakeLLM()
        with patch.object(app, 'llm', model), patch.object(app, 'get_settings', return_value=cfg), \
             patch.object(app, 'get_gemini_key', return_value=''):
            result = asyncio.run(app.game_mode_cloud_fallback({'active': True}))
            self.assertFalse(result['active'])
            self.assertIn('No saved Gemini key', result['reason'])
            self.assertEqual(model.calls, [])
            invalid = asyncio.run(app.game_mode_cloud_fallback({'active': 'yes'}))
            self.assertEqual(invalid.status_code, 400)


    def test_game_override_and_cloud_recovery_then_universal_restore(self):
        cfg={'llm_provider':'ollama','ollama_model':'universal:4b','game_ollama_model':'game:2b'}
        model=FakeLLM()
        with patch.object(app,'llm',model),patch.object(app,'get_settings',return_value=cfg),patch.object(app,'EDITION','companion'),patch('local_model_manager.model_details',return_value={'vision':True}):
            app.app.state.game_cloud_fallback_active=False
            result=asyncio.run(app.game_mode_model({'active':True}))
            self.assertEqual(result['model'],'game:2b');self.assertEqual(model.calls[-1],('local','game:2b'))
            result=asyncio.run(app.game_mode_model({'active':False}))
            self.assertEqual(result['model'],'universal:4b');self.assertEqual(model.calls[-1],('local','universal:4b'))
    def test_text_only_game_override_is_rejected_without_switch(self):
        cfg={'llm_provider':'ollama','ollama_model':'universal:4b','game_ollama_model':'text:2b'}
        model=FakeLLM()
        with patch.object(app,'llm',model),patch.object(app,'get_settings',return_value=cfg),patch.object(app,'EDITION','companion'),patch('local_model_manager.model_details',return_value={'vision':False}):
            app.app.state.game_cloud_fallback_active=False
            result=asyncio.run(app.game_mode_model({'active':True}))
            self.assertEqual(result.status_code,400);self.assertEqual(model.calls,[])


    def test_actual_local_configuration_restores_provider_after_cloud(self):
        from llm import LLM
        instance=object.__new__(LLM)
        instance.provider='gemini';instance.tracking_only=False
        instance._provider_lock=threading.RLock()
        response=Mock();response.json.return_value={'capabilities':['vision']}
        with patch('ollama_runtime.server_for_folder',return_value='http://local.test'),patch('llm.requests.post',return_value=response):
            instance.configure_local('custom-vision:4b')
        self.assertEqual(instance.provider,'ollama');self.assertEqual(instance.vision_model,'custom-vision:4b')
    def test_automatic_fallback_setting_is_respected(self):
        with patch.object(app,'llm',FakeLLM()),patch.object(app,'get_settings',return_value={'game_cloud_auto_enabled':False}):
            result=asyncio.run(app.game_mode_cloud_fallback({'active':True}))
            self.assertFalse(result['active']);self.assertIn('disabled',result['reason'])


if __name__ == '__main__':
    unittest.main()
