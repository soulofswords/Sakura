import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from llm import LLM

# Greetings are answered locally, so this asks something that reaches Ollama.
QUESTION = 'Describe the difference between a retry and a rollback.'


class MissingLocalModelTests(unittest.TestCase):
    """Uninstalled weights are a configuration fact, not a crash to apologise for."""

    def model(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        llm = LLM(Path(holder.name) / 'memory.json')
        llm.configure_provider('ollama')
        llm.model = 'qwen3-vl:4b-instruct'
        return llm

    def test_a_missing_model_names_itself_and_points_at_settings(self):
        llm = self.model()
        with patch('llm.requests.post', return_value=Mock(status_code=404)):
            reply = llm.chat(QUESTION)
        self.assertIn('qwen3-vl:4b-instruct', reply)
        self.assertIn('not installed', reply)
        self.assertIn('Settings > AI', reply)
        self.assertNotIn('Oops', reply)
        self.assertEqual(llm.history, [])

    def test_other_http_failures_keep_the_previous_message(self):
        llm = self.model()
        failure = Mock(status_code=500)
        failure.raise_for_status.side_effect = requests.HTTPError('500 Server Error')
        with patch('llm.requests.post', return_value=failure):
            reply = llm.chat(QUESTION)
        self.assertIn('500', reply)

    def test_warmup_reports_without_raising(self):
        llm = self.model()
        with patch('llm.requests.post', return_value=Mock(status_code=404)):
            llm.warmup()                     # must not raise: the app still starts
        self.assertEqual(llm.history, [])


if __name__ == '__main__':
    unittest.main()
