import unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import Mock
from calendar_chat import CalendarChat
class InterviewTests(unittest.TestCase):
 def test_actual_reported_conversation(self):
  calendar=Mock();calendar.status.return_value={'connected':True};calendar.create_event.return_value={'created':True};alerts=Mock()
  chat=CalendarChat(calendar,alerts,lambda:datetime(2026,10,22,18,tzinfo=timezone(timedelta(hours=5,minutes=30))))
  self.assertIn('end',chat.command('Hello make a schedule for my interview tommorow at 11:30 am.'))
  self.assertIn('end',chat.command('add to my calender it would be still 2 pm something.'))
  reply=chat.command('11:30 am to 2 pm got it')
  self.assertIn('23 October 2026',reply);self.assertIn('11:30 AM',reply);self.assertIn('02:00 PM',reply)
  calendar.create_event.assert_not_called()
  self.assertIn('Added to Google Calendar',chat.command('yes'))
  args=calendar.create_event.call_args.args
  self.assertEqual(args[0],'interview');self.assertIn('2026-10-23T11:30:00+05:30',args[1]);self.assertIn('2026-10-23T14:00:00+05:30',args[2])
 def test_unsupported_request_cannot_fall_through_to_model(self):
  calendar=Mock();calendar.status.return_value={'connected':True};chat=CalendarChat(calendar,Mock())
  self.assertIn('Nothing has been added',chat.command('add my interview to calendar next week'))
  self.assertIn('no confirmed save',chat.command('did you actually add to the calendar'))
  calendar.create_event.assert_not_called()
