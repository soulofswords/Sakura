from local_client import local_request
import unittest
from unittest.mock import Mock, patch
import app as server


class ChatEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_screenshot_messages_work_in_local_and_cloud(self):
        cases={'hello':'Hello!', 'how are u':"I'm ready to chat. How are you?", 'who areu':"I'm Sakura, the AI assistant in this app."}
        for provider in ('local','gemini','openai'):
            model=Mock()
            with patch.object(server,'llm',model), patch.object(server,'get_settings',return_value={'llm_provider':provider}), patch('assistant_commands.run_command',return_value=None), patch('response_evidence.web_retrieve') as web:
                for text,expected in cases.items():
                    result=await server.chat({'text':text,'defer_audio':True})
                    self.assertEqual(result['reply'],expected,(provider,text))
                    self.assertEqual(result['speech_reply'],expected)
                model.chat.assert_not_called();web.assert_not_called()

    async def test_news_uses_same_live_lookup_for_local_and_cloud(self):
        bulletin='21 October 2026, 09:30 AM IST. Recent headlines retrieved now: Mumbai headline - Publisher (Publisher, 2026-10-21T00:17:50+00:00). Source: https://news.google.com/rss/articles/example'
        for provider in ('local','gemini','openai'):
            with self.subTest(provider=provider):
                model=Mock()
                with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={'llm_provider':provider,'news_area':'Maharashtra'}),patch('assistant_commands.run_command',return_value=None),patch('current_information.lookup_with_context',return_value=(bulletin,None)) as lookup:
                    result=await server.chat({'text':'news for Mumbai','defer_audio':True})
                    self.assertEqual(result['reply'],bulletin)
                    self.assertEqual(result['speech_reply'],'21 October 2026, 09:30 AM IST. Here are the headlines: Mumbai headline.')
                    lookup.assert_called_once_with('news for Mumbai',unittest.mock.ANY,'Maharashtra')
                    model.chat.assert_not_called()

    async def test_greeting_does_not_need_generation_or_audio_when_deferred(self):
        model=Mock();model.chat.return_value='';model.reply_language='Hindi'
        speech=Mock()
        with patch.object(server,'llm',model),patch.object(server,'tts',speech),patch.object(server,'get_settings',return_value={}),patch('assistant_commands.run_command',return_value=None),patch('current_information.lookup_with_context',return_value=(None,None)):
            result=await server.chat({'text':'hello','defer_audio':True})
            self.assertEqual(result['reply'],'Hello!')
            model.chat.assert_not_called()
            speech.speak_to_file_async.assert_not_called()
    async def test_vtuber_name_is_validated_saved_and_applied(self):
        import json,tempfile
        from pathlib import Path
        from llm import LLM
        with tempfile.TemporaryDirectory() as folder:
            settings=Path(folder)/'settings.json'
            model=LLM(Path(folder)/'memory.json')
            with patch.object(server,'SETTINGS_FILE',settings),patch.object(server,'llm',model),patch.object(server,'tts',None),patch.object(server,'public_settings',side_effect=lambda s:s):
                response=await server.update_app_settings(local_request(),{'vtuber_name':'  Luna Star  '})
                self.assertTrue(response['ok']);self.assertEqual(model.vtuber_name,'Luna Star')
                self.assertEqual(server.get_settings()['vtuber_name'],'Luna Star')
                self.assertEqual(json.loads(settings.read_text())['vtuber_name'],'Luna Star')
                self.assertEqual(model.assistant_name,'Sakura')
                reopened=LLM(Path(folder)/'other-memory.json');reopened.set_vtuber_name(server.get_settings()['vtuber_name'])
                self.assertEqual(reopened.vtuber_name,'Luna Star')
                for invalid in ['',None,42,'x'*81]:
                    result=await server.update_app_settings(local_request(),{'vtuber_name':invalid})
                    self.assertEqual(result.status_code,400)
    async def test_greeting_uses_safe_dialogue_without_llm(self):
        model = Mock()
        model.chat.return_value = "Hello, Master."
        with patch.object(server, 'llm', model), patch.object(server, 'get_settings', return_value={}), patch('assistant_commands.run_command', return_value=None):
            result = await server.chat({'text': 'hello', 'defer_audio': True})
        self.assertEqual(result['reply'], 'Hello!')
        model.chat.assert_not_called()

    async def test_command_reply_skips_llm_and_screen_validation(self):
        model = Mock()
        with patch.object(server, 'llm', model), patch.object(server, 'get_settings', return_value={'computer_control_enabled': True}), patch('assistant_commands.run_command', return_value='Opening Google Chrome.') as command:
            result = await server.chat({'text': 'open chrome', 'screen_image': 'unused', 'defer_audio': True})
        self.assertEqual(result['reply'], 'Opening Google Chrome.')
        command.assert_called_once_with('open chrome', True, 'Sakura')
        model.chat.assert_not_called()
