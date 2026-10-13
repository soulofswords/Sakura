import unittest
from unittest.mock import Mock, patch
import app as server


class ChatEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_chat_reaches_llm(self):
        model = Mock()
        model.chat.return_value = "Hello, Master."
        with patch.object(server, 'llm', model), patch.object(server, 'get_settings', return_value={}), patch('assistant_commands.run_command', return_value=None):
            result = await server.chat({'text': 'hello', 'defer_audio': True})
        self.assertEqual(result['reply'], 'Hello, Master.')
        model.chat.assert_called_once_with('hello', None)

    async def test_command_reply_skips_llm_and_screen_validation(self):
        model = Mock()
        with patch.object(server, 'llm', model), patch.object(server, 'get_settings', return_value={'computer_control_enabled': True}), patch('assistant_commands.run_command', return_value='Opening Google Chrome.') as command:
            result = await server.chat({'text': 'open chrome', 'screen_image': 'unused', 'defer_audio': True})
        self.assertEqual(result['reply'], 'Opening Google Chrome.')
        command.assert_called_once_with('open chrome', True, 'Sakura')
        model.chat.assert_not_called()
