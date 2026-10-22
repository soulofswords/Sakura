import unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import Mock
from calendar_chat import CalendarChat
class CalendarChatTests(unittest.TestCase):
 def setUp(self):
  self.calendar=Mock();self.calendar.status.return_value={'connected':True};self.calendar.create_event.return_value={'created':True};self.reminders=Mock();self.chat=CalendarChat(self.calendar,self.reminders,lambda:datetime(2026,10,22,tzinfo=timezone(timedelta(hours=5,minutes=30))))
 def test_meeting_needs_end_and_confirmation(self):
  self.assertIn('end',self.chat.command('there is a meeting on 30th November at 2 pm'))
  self.calendar.create_event.assert_not_called()
  self.assertIn('30 November 2026',self.chat.command('3 pm'))
  self.calendar.create_event.assert_not_called()
  self.assertIn('Added',self.chat.command('yes'))
  self.assertEqual(self.calendar.create_event.call_args.kwargs['reminder_minutes'],0)
  self.assertTrue(self.calendar.create_event.call_args.args[1].endswith('+05:30'))
  self.reminders.add.assert_called_once()
  self.assertIsNone(self.chat.command('yes'))
 def test_birthday_asks_time_and_can_cancel(self):
  self.assertIn('What time',self.chat.command('reminder on 25th october mohit birthday'))
  self.assertIn('Say yes',self.chat.command('9 am'))
  self.assertIn('Cancelled',self.chat.command('cancel'))
  self.calendar.create_event.assert_not_called()
 def test_failure_not_retried(self):
  self.chat.command('meeting on 30 November at 2 pm to 3 pm');self.calendar.create_event.side_effect=RuntimeError()
  self.assertIn('could not confirm',self.chat.command('yes'));self.chat.command('yes')
  self.calendar.create_event.assert_called_once();self.reminders.add.assert_not_called()
 def test_unrelated_speech_does_not_save(self):
  self.chat.command('meeting on 30 November at 2 pm to 3 pm')
  self.assertIsNone(self.chat.command('hello'))
  self.calendar.create_event.assert_not_called()
