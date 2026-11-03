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
        with patch.object(server, 'llm', model), patch.object(server, 'get_settings', return_value={'computer_control_enabled': True}), patch('assistant_commands.run_command', return_value='PC status is 13 percent.') as command:
            result = await server.chat({'text': 'pc status', 'screen_image': 'unused', 'defer_audio': True})
        self.assertEqual(result['reply'], 'PC status is 13 percent.')
        command.assert_called_once_with('pc status', True, 'Sakura', 'desktop')
        model.chat.assert_not_called()

    async def test_agent_mode_message_asks_the_same_chat_brain_about_its_task(self):
        model = Mock()
        model.chat.return_value = 'The clone step timed out.'
        settings = {'response_restriction_level': 'off'}
        with patch.object(server, 'llm', model), patch.object(server, 'get_settings', return_value=settings), patch('assistant_commands.run_command', return_value=None), patch('current_information.lookup_with_context', return_value=(None, None)), patch('factual_grounding.gpu_memory_lookup', return_value=None), patch('agent_runtime.runtime.conversation_context', return_value='Goal: clone the repo · status failed') as brief:
            result = await server.chat({'text': 'What happened with my task?', 'defer_audio': True, 'agent_task': 'run-1'})
        self.assertEqual(brief.call_args.args[0], 'run-1')
        self.assertEqual(model.chat.call_args.args[:3], ('What happened with my task?', None, None))
        self.assertEqual(model.chat.call_args.kwargs['agent_task'], 'Goal: clone the repo · status failed')
        self.assertEqual(result['reply'], 'The clone step timed out.')

    async def test_agent_task_brief_is_not_sent_to_the_screen_reaction(self):
        # llm.screen_reaction has no agent_task parameter; passing the brief there would raise.
        import base64, io
        from PIL import Image
        picture = io.BytesIO()
        Image.new('RGB', (64, 64), 'blue').save(picture, format='JPEG')
        frame = base64.b64encode(picture.getvalue()).decode()
        model = Mock()
        model.screen_reaction.return_value = {'reply': 'A blue window is open.'}
        settings = {'response_restriction_level': 'off'}
        with patch.object(server, 'llm', model), patch.object(server, 'get_settings', return_value=settings), patch('assistant_commands.run_command', return_value=None), patch('agent_runtime.runtime.conversation_context', return_value='Goal: clone the repo'):
            await server.chat({'text': 'What is on my screen?', 'defer_audio': True, 'screen_reaction': True, 'agent_task': 'run-1', 'screen_image': frame})
        self.assertEqual(model.screen_reaction.call_args.args[0], frame)
        self.assertNotIn('agent_task', model.screen_reaction.call_args.kwargs)

    async def test_ordinary_companion_chat_has_no_task_brief(self):
        model = Mock()
        model.chat.return_value = 'Sure.'
        settings = {'response_restriction_level': 'off'}
        with patch.object(server, 'llm', model), patch.object(server, 'get_settings', return_value=settings), patch('assistant_commands.run_command', return_value=None), patch('current_information.lookup_with_context', return_value=(None, None)), patch('factual_grounding.gpu_memory_lookup', return_value=None), patch('agent_runtime.runtime.conversation_context') as brief:
            await server.chat({'text': 'Do you like rain?', 'defer_audio': True})
        brief.assert_not_called()
        self.assertEqual(model.chat.call_args.args, ('Do you like rain?', None, None))
        self.assertEqual(model.chat.call_args.kwargs['app_context']['mode'], 'Companion')
        self.assertNotIn('agent_task', model.chat.call_args.kwargs)
