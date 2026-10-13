import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import requests
from llm import LLM

class MemoryTests(unittest.TestCase):
    def test_saved_memory_and_clear(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'memory.json'
            llm = LLM(path)
            with patch.object(llm, '_request', return_value='I will remember that.'):
                llm.chat('My name is Gaurav and I prefer short answers.')
            restored = LLM(path)
            self.assertEqual(restored.history[0]['content'], 'My name is Gaurav and I prefer short answers.')
            restored.clear_history()
            self.assertEqual(LLM(path).history, [])

    def test_older_facts_enter_summary_and_survive_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'memory.json'
            llm = LLM(path)
            llm.history = [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': str(i)} for i in range(40)]
            llm.history[0]['content'] = 'My project is Sakura and my GPU is RTX 3080.'
            calls = []
            def request(messages, **kwargs):
                calls.append(messages)
                return 'User works on Sakura and has an RTX 3080.' if kwargs.get('summarizing') else 'You have an RTX 3080.'
            with patch.object(llm, '_request', side_effect=request):
                llm._refresh_summary()
                llm.chat('What GPU do I have?')
            self.assertIn('RTX 3080', calls[0][1]['content'])
            self.assertIn('RTX 3080', calls[1][1]['content'])
            self.assertIn('RTX 3080', LLM(path).summary)
            self.assertEqual(len(LLM(path).history), 42)

    def test_failure_does_not_save_fake_conversation(self):
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            with patch.object(llm, '_request', side_effect=requests.ConnectionError()):
                llm.chat('hello')
            self.assertEqual(llm.history, [])
            self.assertFalse(llm.memory_path.exists())

if __name__ == '__main__':
    unittest.main()
