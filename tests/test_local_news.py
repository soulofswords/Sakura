import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from current_information import news_query, lookup, lookup_with_context


class LocalNews(unittest.TestCase):
    def test_queries(self):
        cases = [('local news','Maharashtra','Maharashtra India'),
                 ('news near me','Mumbai','Mumbai India'),
                 ('latest news','Maharashtra','Maharashtra India'),
                 ('news in Delhi','Mumbai','delhi'),
                 ('news for Mumbai','Delhi','mumbai'),
                 ('India news','Mumbai','india'),
                 ('technology news','Mumbai','technology'),
                 ('news','',''), ('local news','',None)]
        for text,area,expected in cases:
            with self.subTest(text=text):self.assertEqual(news_query(text,area),expected)

    def test_no_guessed_location(self):
        with patch('current_information.requests.get') as get:
            self.assertIn('Which city or state',lookup('local news'))
            get.assert_not_called()

    def test_india_edition_and_saved_area(self):
        response=Mock(content=b'<rss><channel/></rss>')
        with patch('current_information.requests.get',return_value=response) as get:
            lookup('news')
            self.assertEqual(get.call_args.kwargs['params'],{'hl':'en-IN','gl':'IN','ceid':'IN:en'})
            lookup_with_context('news',None,'Maharashtra')
            self.assertEqual(get.call_args.kwargs['params']['q'],'Maharashtra India when:1d')

    def test_date_time_precedes_headlines_in_ist(self):
        clock=datetime(2026,10,21,20,45,tzinfo=timezone.utc)
        feed=b'''<rss><channel><item><title>Mumbai headline</title>
        <pubDate>Wed, 21 Oct 2026 20:00:00 GMT</pubDate>
        <source url="https://example.com">Publisher</source>
        <link>https://news.google.com/articles/test</link></item></channel></rss>'''
        with patch('current_information.datetime') as dt,patch('current_information.requests.get',return_value=Mock(content=feed)) as get:
            dt.now.return_value=clock
            reply=lookup('news for Mumbai')
            self.assertTrue(reply.startswith('22 October 2026, 02:15 AM IST.'))
            self.assertGreater(reply.index('Mumbai headline'),reply.index('IST.'))
            self.assertEqual(get.call_args.kwargs['params']['q'],'mumbai when:1d')

if __name__=='__main__':unittest.main()
