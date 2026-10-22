import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime
from assistant_commands import run_command
from assistant_reminders import Reminders
from current_information import lookup

class ResponseAudit(unittest.TestCase):
    def test_date_variants(self):
        for text in ["What’s today’s date?", "What's today's date?",'What day is today?','current date']:
            with self.subTest(text=text):self.assertTrue(run_command(text).startswith('Today is'))

    def test_timer_precedes_opening(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Reminders(Path(folder)/'reminders.json',lambda:datetime(2026,10,20,12).timestamp())
            with patch('assistant_reminders.reminders',store),patch('assistant_commands.open_installed_app') as open_app:
                for text in ['Start a five-minute timer','Can you please set a timer for twenty five minutes?','Please set an alarm for three pm']:
                    self.assertIn('set for',run_command(text,True))
                open_app.assert_not_called()
                self.assertEqual(len(store.list()),3)

    def test_current_city_variants_and_short_response(self):
        geo=Mock();geo.json.return_value={'results':[{'name':'Mumbai','country':'India','latitude':19,'longitude':72}]}
        current=Mock();current.json.return_value={'current':{'temperature_2m':30,'time':'2026-10-20T12:00'}}
        for text in ['current weather in Mumbai','weather Mumbai right now','Can you check for me the weather in Mumbai now?']:
            with self.subTest(text=text),patch('current_information.requests.get',side_effect=[geo,current]) as get:
                result=lookup(text)
                self.assertIn('Current weather for Mumbai',result)
                self.assertNotIn('rain chance',result)
                self.assertEqual(get.call_args_list[0].kwargs['params']['name'],'Mumbai')
                self.assertNotIn('daily',get.call_args_list[1].kwargs['params'])
                self.assertEqual(get.call_args_list[0].kwargs['timeout'],(3,5))

    def test_city_without_preposition(self):
        geo=Mock();geo.json.return_value={'results':[]}
        with patch('current_information.requests.get',return_value=geo) as get:
            self.assertIn('could not find',lookup('weather Mumbai'))
            self.assertEqual(get.call_args.kwargs['params']['name'],'Mumbai')

    def test_screen_requests_are_not_live_feed_requests(self):
        with patch('current_information.requests.get') as get:
            self.assertIsNone(lookup('What is the weather on my screen?'))
            self.assertIsNone(lookup('Explain the news in this video'))
            self.assertIsNone(lookup('what is news'))
            get.assert_not_called()

    def test_topic_news_and_network_failures(self):
        import requests
        for text in ['technology news','latest news about gaming']:
            with patch('current_information.requests.get',side_effect=requests.Timeout) as get:
                self.assertIn('could not retrieve',lookup(text))
                self.assertIn('q',get.call_args.kwargs['params'])
                self.assertEqual(get.call_args.kwargs['timeout'],(3,5))

    def test_launch_errors_are_not_success(self):
        with patch('assistant_commands.webbrowser.open',side_effect=OSError('blocked')):
            self.assertIn("couldn't open",run_command('open youtube',True))
        with patch('assistant_commands.sys.platform','win32'),patch('assistant_commands.subprocess.Popen',side_effect=OSError('blocked')):
            self.assertIn('could not start',run_command('open notepad',True))

if __name__=='__main__':unittest.main()
