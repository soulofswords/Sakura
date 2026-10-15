import unittest
from datetime import datetime
from unittest.mock import Mock, patch
from current_information import lookup, lookup_with_context


class WeatherDates(unittest.TestCase):
    def test_exact_user_request_and_location_followup(self):
        geo=Mock();geo.json.return_value={'results':[{'name':'New Delhi','country':'India','latitude':28.6,'longitude':77.2}]}
        forecast=Mock();forecast.json.return_value={'daily':{'time':['2026-10-20'],'temperature_2m_min':[23],'temperature_2m_max':[31],'precipitation_probability_max':[10]}}
        with patch('current_information.datetime') as clock, patch('current_information.requests.get',side_effect=[geo,forecast,geo,forecast]) as get:
            clock.now.return_value=datetime(2026,10,14)
            reply=lookup('can u tell me weather of Delhi on 20th october 2026')
            self.assertIn('2026-10-20: 23 to 31',reply)
            self.assertEqual(get.call_args_list[0].kwargs['params']['name'],'Delhi')
            self.assertEqual(get.call_args_list[1].kwargs['params']['start_date'],'2026-10-20')
            question,pending=lookup_with_context('weather on 20th october 2026')
            self.assertIn('Which city',question)
            reply,pending=lookup_with_context('New Delhi',pending)
            self.assertIn('2026-10-20: 23 to 31',reply)
            self.assertIsNone(pending)
            self.assertEqual(get.call_count,4)

    def test_invalid_and_outside_horizon_never_generate_guesses(self):
        with patch('current_information.datetime') as clock, patch('current_information.requests.get') as get:
            clock.now.return_value=datetime(2026,10,14)
            self.assertIn('invalid',lookup('weather of Delhi on 32nd october 2026'))
            self.assertIn('outside',lookup('weather of Delhi on 20th december 2026'))
            reply,pending=lookup_with_context('hello','on 2026-10-20')
            self.assertIsNone(reply)
            self.assertIsNone(pending)
            get.assert_not_called()
            self.assertIsNone(lookup('hello'))


if __name__=='__main__':unittest.main()
