from datetime import datetime,timedelta,timezone
import unittest
from unittest.mock import Mock,patch
from calendar_chat import CalendarChat

class CalendarAgendaTests(unittest.TestCase):
    def setUp(self):
        self.calendar=Mock()
        self.calendar.status.return_value={'connected':True}
        self.calendar.list_events.return_value={'ok':True,'events':[
            {'summary':'Interview','start':{'dateTime':'2026-10-25T06:00:00Z'},'end':{'dateTime':'2026-10-25T08:30:00Z'}},
            {'summary':'Mohit birthday','start':{'date':'2026-10-25'},'end':{'date':'2026-10-26'}},
        ]}
        self.now=datetime(2026,10,25,8,tzinfo=timezone(timedelta(hours=5,minutes=30)))
        self.alerts=Mock()
        self.chat=CalendarChat(self.calendar,self.alerts,lambda:self.now)

    def test_daily_plan_reads_the_connected_calendar_in_local_time(self):
        reply=self.chat.command("what's my plan for today?")
        self.assertIn('11:30 AM - 2:00 PM: Interview',reply)
        self.assertIn('All day: Mohit birthday',reply)
        self.assertIn('UTC+05:30',reply)
        self.calendar.list_events.assert_called_once_with(time_min='2026-10-25T00:00:00+05:30',time_max='2026-10-26T00:00:00+05:30',max_results=50)
        self.calendar.create_event.assert_not_called();self.alerts.add.assert_not_called()
        self.assertIsNone(self.chat.pending)
        self.assertNotIn('vibe',reply)

    def test_common_schedule_questions_read_instead_of_starting_an_event(self):
        for text in ["what’s my plan for today?",'show my calendar today','what is my schedule tomorrow','what am I doing today','do I have anything today','my agenda','any meetings today?','what are my plans this week?']:
            with self.subTest(text=text):
                self.assertIn('Google Calendar schedule',self.chat.command(text))
                self.assertIsNone(self.chat.pending)
        self.calendar.create_event.assert_not_called()

    def test_tomorrow_and_week_queries_have_the_right_bounds(self):
        self.chat.command('show my schedule tomorrow')
        self.assertEqual(self.calendar.list_events.call_args.kwargs['time_min'],'2026-10-26T00:00:00+05:30')
        self.chat.command('show my calendar this week')
        self.assertEqual(self.calendar.list_events.call_args.kwargs['time_min'],'2026-10-19T00:00:00+05:30')
        self.assertEqual(self.calendar.list_events.call_args.kwargs['time_max'],'2026-10-26T00:00:00+05:30')

    def test_no_events_is_not_an_excuse_to_invent_plans(self):
        self.calendar.list_events.return_value={'ok':True,'events':[]}
        self.assertIn('no events on your connected Google Calendar',self.chat.command("what's my plan for today"))

    def test_an_explicit_read_date_is_not_silently_replaced_with_today(self):
        self.chat.command('show my calendar for 30 November 2026')
        self.assertEqual(self.calendar.list_events.call_args.kwargs['time_min'],'2026-11-30T00:00:00+05:30')
        self.assertIn('date is invalid',self.chat.command('show my calendar for 31 November'))

    def test_disconnected_and_failed_reads_return_truthful_status(self):
        self.calendar.status.return_value={'connected':False}
        self.assertIn('not connected',self.chat.command('show my schedule today'))
        self.calendar.list_events.assert_not_called()
        self.calendar.status.return_value={'connected':True}
        self.calendar.list_events.side_effect=RuntimeError('private detail')
        reply=self.chat.command("what's my plan for today")
        self.assertIn('could not read',reply);self.assertNotIn('private detail',reply)
        self.calendar.create_event.assert_not_called()

    def test_agenda_read_does_not_approve_a_draft_event(self):
        self.chat.command('meeting tomorrow at 11 am to 12 pm')
        self.assertEqual(self.chat.pending['stage'],'confirm')
        self.chat.command('show my calendar today')
        self.assertIn('Say yes',self.chat.command('yes'))
        self.calendar.create_event.assert_not_called()

    def test_normal_advice_is_not_a_calendar_read(self):
        for text in ['how to plan my day','what is the plan for this project','hello']:
            self.assertIsNone(self.chat.command(text))
        self.calendar.list_events.assert_not_called()

    def test_command_router_handles_the_reported_question_without_computer_control(self):
        from assistant_commands import run_command
        with patch('calendar_chat._instance',self.chat):
            self.assertIn('Interview',run_command("what's my plan for today?",computer_access=False))
        self.calendar.create_event.assert_not_called()


class CalendarAgendaEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_daily_plan_uses_calendar_for_local_and_cloud_without_model_generation(self):
        import app
        for provider in ('ollama','gemini','openai'):
            calendar=Mock();calendar.status.return_value={'connected':True}
            calendar.list_events.return_value={'ok':True,'events':[{'summary':'Interview','start':{'dateTime':'2026-10-25T06:00:00Z'},'end':{'dateTime':'2026-10-25T08:30:00Z'}}]}
            now=datetime(2026,10,25,8,tzinfo=timezone(timedelta(hours=5,minutes=30)))
            chat=CalendarChat(calendar,Mock(),lambda:now)
            model=Mock()
            with self.subTest(provider=provider),patch.object(app,'llm',model),patch.object(app,'get_settings',return_value={'llm_provider':provider}),patch('calendar_chat._instance',chat):
                result=await app.chat({'text':"what's my plan for today?",'defer_audio':True})
                self.assertIn('11:30 AM - 2:00 PM: Interview',result['reply'])
                calendar.list_events.assert_called_once()
                calendar.create_event.assert_not_called()
                model.chat.assert_not_called()
