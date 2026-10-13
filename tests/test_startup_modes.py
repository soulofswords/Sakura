import os
import unittest
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient
import app


class StartupModeTests(unittest.TestCase):
    def check_mode(self, mode, provider, tracking):
        config = app.get_settings()
        config.update(llm_provider=provider, vtuber_tracking_only=tracking,
                      selected_voice='sakura_ava', rvc_model='')
        model = Mock()
        model.warmup.return_value = None
        model.configure_local.return_value = None
        with patch.dict(os.environ, {'SAKURA_DESKTOP':'1', 'SAKURA_START_MODE':mode,
                                    'SAKURA_START_GEMINI_KEY':'synthetic-test-key' if mode=='gemini' else ''}), \
             patch.object(app, 'get_settings', return_value=config), \
             patch.object(app, 'save_settings', return_value=config) as save, \
             patch.object(app, 'get_gemini_key', return_value='synthetic-test-key'), \
             patch.object(app, 'set_gemini_key') as protect, \
             patch('llm.LLM', return_value=model), patch('tts.TextToSpeech'), \
             patch.object(app, 'sync_selected_rvc_service', new_callable=AsyncMock), \
             patch('rvc_manager.stop_rvc_service'), patch('youtube_chat.chat.stop'), \
             patch('ollama_runtime.stop'):
            with TestClient(app.app) as client:
                self.assertEqual(client.get('/api/tracking/mode').json()['tracking_only'], tracking)
                self.assertEqual(client.get('/api/tracking/mode').json()['startup_mode'], mode)
                self.assertEqual(model.configure_local.call_count, 1 if mode=='local' else 0)
                if tracking:
                    self.assertIsNone(app.app.state.llm_warmup)
                    self.assertEqual(client.post('/api/chat', json={'text':'hello'}).status_code, 409)
                self.assertEqual(save.call_args.args[0]['vtuber_tracking_only'], tracking)
                if mode=='gemini':
                    protect.assert_called_once_with('synthetic-test-key')
                    model.configure_provider.assert_called_once_with('gemini', config['gemini_model'], 'synthetic-test-key')

    def test_local_starts_local_runtime(self):
        self.check_mode('local', 'ollama', False)

    def test_gemini_protects_key_and_does_not_start_local_runtime(self):
        self.check_mode('gemini', 'gemini', False)

    def test_vtuber_never_warms_local_model_and_blocks_ai(self):
        self.check_mode('vtuber', 'ollama', True)

