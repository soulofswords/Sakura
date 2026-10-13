import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from llm import LLM

class ReactionRepeatTests(unittest.TestCase):
    def test_cooldown_repeat_context_and_new_event(self):
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            with patch('llm.time.monotonic', return_value=100), patch.object(llm, '_request', return_value='Master, that was an amazing shot!') as request:
                self.assertIn('amazing', llm.screen_reaction('image'))
                self.assertEqual(llm.screen_reaction('image'), '[QUIET]')
                self.assertEqual(request.call_count, 1)
            with patch('llm.time.monotonic', return_value=131), patch.object(llm, '_request', return_value='Wow, that was an amazing shot, Master!') as request:
                self.assertEqual(llm.screen_reaction('image'), '[QUIET]')
                self.assertIn('that was an amazing shot', request.call_args.args[0][0]['content'])
            with patch('llm.time.monotonic', return_value=162), patch.object(llm, '_request', return_value='The exit just opened on your left.'):
                self.assertEqual(llm.screen_reaction('image'), 'The exit just opened on your left.')
            self.assertEqual(llm.history, [])

    def test_initial_check_bypasses_cooldown(self):
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            with patch.object(llm, '_request', return_value='I can see the game menu.'):
                llm.screen_reaction('image')
                self.assertNotEqual(llm.screen_reaction('image', True), '[QUIET]')
