import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from assistant_reminders import Reminders


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.now=datetime(2026,10,15,10,0).timestamp()
        self.store=Reminders(Path(self.folder.name)/'reminders.json',lambda:self.now)

    def test_spoken_and_typed_durations(self):
        for text,seconds in [('make a 5 min timer',300),('set a five minute timer',300),('can u set a twenty five minute timer',1500),('start a timer for 1 hour 30 minutes',5400)]:
            with self.subTest(text=text):
                self.assertIn('Timer set',self.store.command(text))
                self.assertEqual(self.store.list()[-1]['due'],self.now+seconds)
        self.assertIn('positive',self.store.command('set a -5 minute timer'))
        self.assertIn('duration',self.store.command('set a zero minute timer'))

    def test_persist_fire_snooze_and_dismiss(self):
        self.store.command('set a 5 second timer');identifier=self.store.list()[0]['id']
        self.now+=6
        reopened=Reminders(self.store.path,lambda:self.now)
        self.assertEqual(reopened.list()[0]['status'],'ringing')
        self.assertTrue(reopened.dismiss(identifier,True))
        self.assertEqual(reopened.list()[0]['remaining'],300)
        self.assertEqual(reopened.list()[0]['status'],'scheduled')
        self.assertTrue(reopened.dismiss(identifier));self.assertEqual(reopened.list(),[])

    def test_alarm_local_time_and_next_day(self):
        self.assertIn('03:00 PM',self.store.command('set an alarm for 3 pm'))
        self.assertEqual(self.store.list()[-1]['due'],datetime(2026,10,15,15).timestamp())
        self.assertIn('16 October',self.store.command('set an alarm for 9 am'))
        self.assertIn('03:00 PM',self.store.command('set an alarm for three pm tomorrow'))
        self.assertIn('passed',self.store.command('set an alarm for 9 am today'))
        self.assertIn('invalid',self.store.command('set an alarm for 25:90'))
        self.assertIn('What time',self.store.command('set an alarm for 3'))

    def test_list_cancel_and_unrelated_conversation(self):
        self.assertIsNone(self.store.command('tell me about alarm clocks'))
        self.store.command('make a five minute timer');self.store.command('make a ten minute timer')
        self.assertIn('Active timers',self.store.command('show my timers'))
        self.assertIn('Cancelled',self.store.command('cancel the timer'))
        self.assertEqual(len(self.store.list()),1)
        self.store.command('cancel all timers');self.assertEqual(self.store.list(),[])
        self.assertIn('no active',self.store.command('list alarms'))

    def test_commands_do_not_require_ai_or_computer_control(self):
        from assistant_commands import run_command
        with patch('assistant_reminders.reminders',self.store):
            self.assertIn('Timer set',run_command('make a 5 min timer',False))

    def test_polite_spoken_commands_use_shared_normalization(self):
        from assistant_commands import run_command
        with patch('assistant_reminders.reminders',self.store):
            for phrase in ['Okay, can you please make a five minute timer?',
                           'Hey Luna, start a timer for 5 seconds please.',
                           'I want you to set a 2 minute timer for me']:
                self.assertIn('Timer set',run_command(phrase,False,'Luna'))
            for phrase in ['Okay, can you set an alarm 3 PM?',
                           'Hey Luna, please put an alarm at three p. m. tomorrow']:
                self.assertIn('Alarm set',run_command(phrase,False,'Luna'))
            self.assertEqual(len(self.store.list()),5)


class ReminderEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_sets_real_timer_and_endpoint_fires_and_dismisses(self):
        import app as server
        with tempfile.TemporaryDirectory() as folder:
            now=[datetime(2026,10,15,10).timestamp()]
            store=Reminders(Path(folder)/'reminders.json',lambda:now[0])
            with patch('assistant_reminders.reminders',store), patch.object(server,'llm',None), patch.object(server,'get_settings',return_value={}), patch.object(server,'EDITION','companion'), patch.object(server.app.state,'tracking_only',False,create=True):
                result=await server.chat({'text':'make a 5 sec timer','defer_audio':True})
                self.assertIn('Timer set',result['reply'])
                now[0]+=6
                alerts=await server.list_reminders()
                self.assertEqual(alerts['items'][0]['status'],'ringing')
                result=await server.dismiss_reminder({'id':alerts['items'][0]['id']})
                self.assertTrue(result['ok']);self.assertEqual((await server.list_reminders())['items'],[])


if __name__=='__main__':unittest.main()
