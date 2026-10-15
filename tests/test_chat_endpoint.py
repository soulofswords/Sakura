import unittest
from unittest.mock import Mock, patch
import app as server


class ChatEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_quality_failure_is_an_error_not_spoken_filler(self):
        model=Mock();model.chat.return_value='';model.reply_language='Hindi'
        speech=Mock()
        with patch.object(server,'llm',model),patch.object(server,'tts',speech),patch.object(server,'get_settings',return_value={}),patch('assistant_commands.run_command',return_value=None),patch('current_information.lookup_with_context',return_value=(None,None)):
            result=await server.chat({'text':'क्या हुआ?','defer_audio':True})
            self.assertEqual(result.status_code,503)
            self.assertIn('जवाब',result.body.decode())
            speech.speak_to_file_async.assert_not_called()
    async def test_vtuber_name_is_validated_saved_and_applied(self):
        import json,tempfile
        from pathlib import Path
        from llm import LLM
        with tempfile.TemporaryDirectory() as folder:
            settings=Path(folder)/'settings.json'
            model=LLM(Path(folder)/'memory.json')
            with patch.object(server,'SETTINGS_FILE',settings),patch.object(server,'llm',model),patch.object(server,'tts',None),patch.object(server,'public_settings',side_effect=lambda s:s):
                response=await server.update_app_settings({'vtuber_name':'  Luna Star  '})
                self.assertTrue(response['ok']);self.assertEqual(model.vtuber_name,'Luna Star')
                self.assertEqual(server.get_settings()['vtuber_name'],'Luna Star')
                self.assertEqual(json.loads(settings.read_text())['vtuber_name'],'Luna Star')
                self.assertEqual(model.assistant_name,'Sakura')
                reopened=LLM(Path(folder)/'other-memory.json');reopened.set_vtuber_name(server.get_settings()['vtuber_name'])
                self.assertEqual(reopened.vtuber_name,'Luna Star')
                for invalid in ['',None,42,'x'*81]:
                    result=await server.update_app_settings({'vtuber_name':invalid})
                    self.assertEqual(result.status_code,400)
    async def test_normal_chat_reaches_llm(self):
        model = Mock()
        model.chat.return_value = "Hello, Master."
        with patch.object(server, 'llm', model), patch.object(server, 'get_settings', return_value={}), patch('assistant_commands.run_command', return_value=None):
            result = await server.chat({'text': 'hello', 'defer_audio': True})
        self.assertEqual(result['reply'], 'Hello, Sir.')
        model.chat.assert_called_once_with('hello', None)

    async def test_command_reply_skips_llm_and_screen_validation(self):
        model = Mock()
        with patch.object(server, 'llm', model), patch.object(server, 'get_settings', return_value={'computer_control_enabled': True}), patch('assistant_commands.run_command', return_value='Opening Google Chrome.') as command:
            result = await server.chat({'text': 'open chrome', 'screen_image': 'unused', 'defer_audio': True})
        self.assertEqual(result['reply'], 'Opening Google Chrome.')
        command.assert_called_once_with('open chrome', True, 'Sakura')
        model.chat.assert_not_called()
