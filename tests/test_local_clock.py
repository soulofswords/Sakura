import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import Mock,patch

from assistant_commands import run_command
from llm import LLM
from local_clock import clock_context


NOW=datetime(2026,10,22,15,7,tzinfo=timezone(timedelta(hours=5,minutes=30),'IST'))


class LocalClockTests(unittest.TestCase):
    def test_compound_date_and_history_uses_clock_and_sources(self):
        from local_clock import clock_command
        now=NOW.replace(day=25)
        reply=Mock()
        reply.json.return_value={'events':[{'year':2001,'text':'A documented event.',
            'pages':[{'content_urls':{'desktop':{'page':'https://en.wikipedia.org/wiki/Example'}}}]}]}
        with patch('local_clock.local_now',return_value=now),patch('requests.get',return_value=reply):
            answer=clock_command("what's the date today. and anything historical happened today")
        self.assertIn('Sunday, 25 October 2026',answer)
        self.assertIn('2001: A documented event.',answer)
        self.assertIn('https://en.wikipedia.org/wiki/Example',answer)

    def test_history_lookup_failure_does_not_claim_nothing_happened(self):
        import requests
        from local_clock import clock_command
        with patch('local_clock.local_now',return_value=NOW),patch('requests.get',side_effect=requests.Timeout):
            answer=clock_command("what's the date today and anything historical happened today")
        self.assertIn('22 October 2026',answer)
        self.assertIn("couldn't retrieve",answer)
        self.assertNotIn('Nothing major',answer)

    def test_natural_clock_and_date_queries_use_system_reading(self):
        with patch('local_clock.local_now',return_value=NOW):
            for query in ('what time is it','do u know what time it is now','can you check the clock','please read the time'):
                self.assertEqual(run_command(query),"It's 3:07 PM.",query)
            for query in ("what is today's date",'what date is it','what day is today','check the date'):
                self.assertEqual(run_command(query),'Today is Thursday, 22 October 2026.',query)
            self.assertEqual(run_command('date and time'),'Thursday, 22 October 2026, 3:07 PM.')
            for query in ["so tell me what's the date and time now","can you tell me the date and time now","what is the date and time right now"]:
                self.assertEqual(run_command(query),'Thursday, 22 October 2026, 3:07 PM.',query)
            self.assertIn('UTC+0530',clock_context())
            for query in ('what time does the interview start','what is the date of my interview','tell me about time travel'):
                self.assertIsNone(run_command(query),query)

    def test_local_and_cloud_receive_fresh_clock_without_web(self):
        for provider in ('ollama','gemini','openai'):
            with tempfile.TemporaryDirectory() as folder:
                model=LLM(Path(folder)/'memory.json');model.provider=provider
                result=Mock(status_code=200);result.json.return_value={'message':{'content':'Good luck with the interview.'}}
                with patch('local_clock.local_now',return_value=NOW),patch('llm.requests.post',return_value=result) as local,patch.object(model,'_request_gemini',return_value='Good luck with the interview.') as gemini,patch('cloud_api.request',return_value='Good luck with the interview.') as cloud:
                    self.assertEqual(model._request_raw([{'role':'user','content':'I have an interview.'}]),'Good luck with the interview.')
                messages=local.call_args.kwargs['json']['messages'] if provider=='ollama' else gemini.call_args.args[0] if provider=='gemini' else cloud.call_args.args[3]
                rules=' '.join(m['content'] for m in messages if m['role']=='system')
                self.assertIn('Thursday, 22 October 2026, 03:07 PM IST',rules)
                self.assertIn('do not claim you cannot',rules)
                self.assertIn('do not volunteer time/date',rules)


if __name__=='__main__':unittest.main()
