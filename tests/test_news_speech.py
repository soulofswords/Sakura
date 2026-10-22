import unittest
from spoken_text import clean_news_for_speech
from tts import polish_spoken_text


class NewsSpeech(unittest.TestCase):
    def test_keep_bulletin_time_and_headlines_without_metadata(self):
        chat=('21 October 2026, 07:06 AM IST. Recent headlines retrieved now: '
              'Bengaluru–Mumbai train launch date - The Hindu (The Hindu, 2026-10-20T11:08:05+00:00). Source: https://www.thehindu.com '
              'Mumbai: Meeting - NDTV (NDTV, 2026-10-21T00:17:50+00:00). Source: https://www.ndtv.com')
        expected='21 October 2026, 07:06 AM IST. Here are the headlines: Bengaluru–Mumbai train launch date. Mumbai: Meeting.'
        self.assertEqual(clean_news_for_speech(chat),expected)
        self.assertEqual(polish_spoken_text(chat),expected)
        self.assertIn('Source:',chat)

    def test_regular_dialogue_and_dates_preserved(self):
        for text in ['The meeting is on 21 October at 7 AM.', 'Use https://example.com as the source.', 'I like NDTV.']:
            self.assertEqual(clean_news_for_speech(text),text)

    def test_headline_parentheses_are_preserved(self):
        text='Recent headlines retrieved now: Mumbai (city) update - Publisher (Publisher, 2026-10-21T00:17:50+00:00). Source: https://example.com'
        self.assertEqual(clean_news_for_speech(text),'Here are the headlines: Mumbai (city) update.')

if __name__=='__main__':unittest.main()
