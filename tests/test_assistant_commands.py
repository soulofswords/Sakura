import unittest
from unittest.mock import patch
from assistant_commands import run_command


class CommandTests(unittest.TestCase):
    def test_chrome_launch_is_explicit_and_permission_gated(self):
        with patch('assistant_commands.subprocess.Popen') as launch, patch('assistant_commands.Path.is_file', return_value=True):
            self.assertIn('Enable computer access', run_command('open google chrome', False))
            launch.assert_not_called()
            self.assertEqual(run_command('Can you please open Google Chrome?', True), 'Opening Google Chrome.')
            self.assertFalse(launch.call_args.kwargs['shell'])
            self.assertIn('--new-window', launch.call_args.args[0])
    def test_access_disabled_does_not_open_browser(self):
        with patch('assistant_commands.webbrowser.open') as browser:
            self.assertIn('Enable computer access', run_command('open youtube'))
            browser.assert_not_called()

    def test_search_is_encoded_and_spoken(self):
        with patch('assistant_commands.webbrowser.open', return_value=True) as browser:
            self.assertEqual(run_command('Search Google for cats & dogs', True), 'Opening Google search.')
            browser.assert_called_once_with('https://www.google.com/search?q=cats+%26+dogs', new=2)

    def test_time_and_unrecognized_conversation(self):
        self.assertTrue(run_command('what time is it').startswith("It's "))
        self.assertIsNone(run_command('tell me about cats'))

    def test_natural_time_requests(self):
        for phrase in ["Can you tell me what time it is?", 'What is the time now?',
                       'Hey Luna, please tell me the current time.', 'Say the time',
                       "What's the time right now?"]:
            with self.subTest(phrase=phrase):
                self.assertTrue(run_command(phrase,False,'Luna').startswith("It's "))
        for phrase in ['what time does the movie start', 'tell me about time travel',
                       'say time flies']:
            self.assertIsNone(run_command(phrase))

    def test_spoken_youtube_requests(self):
        with patch('assistant_commands.webbrowser.open', return_value=True) as browser:
            for phrase in ['Ok then, what can you open youtube?', 'Okay, can you open YouTube?', 'Hey Sakura, please open you tube.']:
                with self.subTest(phrase=phrase):
                    self.assertEqual(run_command(phrase, True), 'Opening YouTube.')
            self.assertEqual(browser.call_count, 3)

    def test_plain_search_and_youtube_search(self):
        with patch('assistant_commands.webbrowser.open', return_value=True) as browser:
            self.assertEqual(run_command('Okay, search what is Samsung.', True), 'Opening Google search.')
            browser.assert_called_with('https://www.google.com/search?q=what+is+samsung', new=2)
            for phrase in ['search youtube for cats', 'search for cats on youtube', 'open youtube and search for cats']:
                self.assertEqual(run_command(phrase, True), 'Opening YouTube search.')
                browser.assert_called_with('https://www.youtube.com/results?search_query=cats', new=2)

    def test_missing_search_query_and_normal_questions(self):
        with patch('assistant_commands.webbrowser.open') as browser:
            self.assertEqual(run_command('Ok then do a search.', True), 'What would you like me to search for?')
            self.assertIsNone(run_command('What is an email?', True))
            self.assertIsNone(run_command('Can you explain how search works?', True))
            self.assertIn('Enable computer access', run_command('Okay, search for cats', False))
            browser.assert_not_called()
