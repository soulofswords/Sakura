import socket
import time
import unittest
from unittest.mock import Mock, patch

import agent_web


PAGE = """<html><body>
<tr><td class='result-link'><a rel="nofollow" href="https://lite.duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fcv&amp;rut=abc">Example CV guide</a></td></tr>
<tr><td class='result-snippet'>How to write a <b>resume</b> that gets read.</td></tr>
<tr><td class='result-link'><a rel="nofollow" href="https://example.org/interview">Interview prep</a></td></tr>
<tr><td class='result-snippet'>Questions to expect at the <i>interview</i>.</td></tr>
<tr><td class='result-link'><a rel="nofollow" href="http://127.0.0.1:8765/api/agent/state">Local panel</a></td></tr>
<tr><td class='result-snippet'>Should never be returned.</td></tr>
</body></html>"""

PUBLIC = [(2, 1, 0, '', ('93.184.216.34', 0))]


def response(text=PAGE, status=200, **headers):
    item = Mock()
    item.text = text
    item.status_code = status
    item.headers = {'content-type': 'text/html', **headers}
    item.raw.stream = Mock(return_value=[text.encode()])
    return item


def page(body=b'<html><body><p>Page text</p></body></html>', status=200, **headers):
    item = Mock()
    item.status_code = status
    item.headers = {'content-type': 'text/html', **headers}
    item.raw.stream = Mock(return_value=[body[i:i + 4096] for i in range(0, len(body), 4096)])
    return item


class WebToolTests(unittest.TestCase):
    def test_public_fetch_disables_ambient_proxy_routing(self):
        with patch('agent_web.requests.get', return_value=page()) as get:
            agent_web.fetch('https://example.com/')
        self.assertFalse(get.call_args.kwargs['allow_redirects'])
        self.assertEqual(get.call_args.kwargs['proxies'], {'http': '', 'https': '', 'all': ''})

    def setUp(self):
        # Keep real DNS out of these tests; example.com resolves to a public host.
        self.dns = patch('agent_web.socket.getaddrinfo', return_value=list(PUBLIC))
        self.dns.start()
        self.addCleanup(self.dns.stop)

    @staticmethod
    def wiki(hits=None):
        item = Mock()
        item.raise_for_status = Mock()
        item.json = Mock(return_value={'query': {'search': hits if hits is not None else [
            {'title': 'Curriculum vitae', 'snippet': 'A <span class="searchmatch">resume</span> lists work.', 'pageid': 7351255}]}})
        return item

    def test_search_unwraps_redirects_and_drops_local_addresses(self):
        with patch('agent_web.requests.post', return_value=response()):
            results = agent_web.search('resume format')['results']
        self.assertEqual([item['url'] for item in results], ['https://example.com/cv', 'https://example.org/interview'])
        self.assertEqual(results[0]['title'], 'Example CV guide')

    def test_each_result_keeps_its_own_snippet(self):
        with patch('agent_web.requests.post', return_value=response()):
            results = agent_web.search('resume format')['results']
        self.assertIn('resume', results[0]['snippet'])
        self.assertNotIn('interview', results[0]['snippet'])
        self.assertIn('interview', results[1]['snippet'])
        self.assertNotIn('never', results[1]['snippet'])

    def test_a_challenge_page_falls_through_to_the_next_provider(self):
        with patch('agent_web.requests.post', return_value=response('<html>Anomaly detected</html>', status=202)), \
                patch('agent_web.requests.get', return_value=self.wiki()) as get:
            found = agent_web.search('resume format')
        self.assertEqual(found['provider'], 'Wikipedia')
        self.assertEqual(get.call_args.kwargs['params']['srsearch'], 'resume format')
        self.assertEqual(found['results'][0]['url'], 'https://en.wikipedia.org/?curid=7351255')

    def test_search_reports_failure_when_every_provider_fails(self):
        with patch('agent_web.requests.post', return_value=response('<html>Anomaly detected</html>', status=202)), \
                patch('agent_web.requests.get', side_effect=agent_web.requests.ConnectionError):
            with self.assertRaisesRegex(ValueError, 'Web search is unavailable'):
                agent_web.search('resume format')

    def test_no_results_is_an_answer_not_an_error(self):
        with patch('agent_web.requests.post', return_value=response('<html>We had no results for that.</html>')), \
                patch('agent_web.requests.get', return_value=self.wiki(hits=[])):
            self.assertEqual(agent_web.search('zzzxq'),
                             {'ok': True, 'results': [], 'note': 'No public, readable results were found for that query.'})

    @staticmethod
    def brave(items=None):
        item = Mock()
        item.raise_for_status = Mock()
        item.json = Mock(return_value={'web': {'results': items if items is not None else [
            {'title': 'RTX 5090 | NVIDIA', 'url': 'https://www.nvidia.com/en-us/rtx-5090/',
             'description': '24 GB GDDR7? No - <b>32 GB</b> GDDR7.'},
            {'title': 'Local panel', 'url': 'http://127.0.0.1:8765/api/agent/state', 'description': 'never'}]}})
        return item

    def test_brave_is_the_first_provider_when_a_key_is_saved(self):
        with patch('agent_web.requests.get', return_value=self.brave()) as get, \
                patch('agent_web.requests.post') as scraped:
            found = agent_web.search('5090 vram', credentials=('', '', 'synthetic-brave-key'))
        self.assertEqual(found['provider'], 'Brave Search')
        self.assertEqual([entry['url'] for entry in found['results']], ['https://www.nvidia.com/en-us/rtx-5090/'])
        self.assertEqual(found['results'][0]['snippet'], '24 GB GDDR7? No - 32 GB GDDR7.')
        self.assertEqual(get.call_args.kwargs['headers']['X-Subscription-Token'], 'synthetic-brave-key')
        scraped.assert_not_called()

    def test_a_rate_limited_provider_falls_through_to_the_next_one(self):
        limited = Mock()
        limited.raise_for_status.side_effect = agent_web.requests.HTTPError('429')
        with patch('agent_web.requests.get', side_effect=[limited, self.wiki()]):
            found = agent_web.search('5090 vram', credentials=('', '', 'synthetic-brave-key'))
        self.assertEqual(found['provider'], 'Wikipedia')

    def test_google_grounding_is_tried_first_when_a_gemini_key_exists(self):
        payload = {'candidates': [{'content': {'parts': [{'text': 'Here are the sources.'}]},
                                   'groundingMetadata': {'groundingChunks': [
                                       {'web': {'title': 'Example CV guide', 'uri': 'https://example.com/cv'}},
                                       {'searchQuery': {'query': 'resume format'}},
                                       {'web': {'title': 'Local panel', 'uri': 'http://127.0.0.1:8765/x'}}],
                                       'groundingSupports': [{'groundingChunkIndices': [0],
                                                              'segment': {'text': 'Lead with measurable <b>impact</b>.'}}]}}]}
        item = Mock(); item.raise_for_status = Mock(); item.json = Mock(return_value=payload)
        with patch('agent_web.requests.post', return_value=item) as post, \
                patch('agent_web.requests.get') as keyless:
            found = agent_web.search('resume format', credentials=('synthetic-key', 'gemini-flash-latest'))
        self.assertEqual(found['provider'], 'Google Search via Gemini')
        self.assertEqual([entry['url'] for entry in found['results']], ['https://example.com/cv'])
        self.assertEqual(found['results'][0]['snippet'], 'Lead with measurable impact.')
        self.assertEqual(post.call_args.kwargs['json']['tools'], [{'google_search': {}}])
        self.assertEqual(post.call_args.kwargs['headers'], {'x-goog-api-key': 'synthetic-key'})
        keyless.assert_not_called()

    def test_grounding_falls_back_when_the_model_rejects_the_search_tool(self):
        failure = Mock(); failure.raise_for_status.side_effect = agent_web.requests.HTTPError('400 unsupported')
        challenged = response('<html>Anomaly detected</html>', status=202)
        with patch('agent_web.requests.post', side_effect=[failure, challenged]) as post, \
                patch('agent_web.requests.get', return_value=self.wiki()):
            found = agent_web.search('resume format', credentials=('synthetic-key', 'gemini-2.0-flash'))
        self.assertEqual(found['provider'], 'Wikipedia')
        self.assertEqual(post.call_count, 2)

    def test_empty_and_overlong_queries_are_refused(self):
        for query in ('', '   ', 'x' * 301):
            with self.assertRaises(ValueError):
                agent_web.search(query)

    def test_loopback_private_and_non_http_targets_cannot_be_fetched(self):
        for url in ('http://127.0.0.1:8765/api/agent/state', 'http://192.168.1.1/admin',
                    'ftp://example.com/file', 'https://user:pass@example.com/',
                    'http://localhost/x', 'http://metadata.google.internal/computeMetadata/v1/'):
            with self.assertRaises(ValueError):
                agent_web.fetch(url)

    def test_binary_responses_are_not_returned_as_text(self):
        with patch('agent_web.requests.get', return_value=response(status=200, **{'content-type': 'application/pdf'})):
            with self.assertRaises(ValueError):
                agent_web.fetch('https://example.com/paper.pdf')

    def test_fetch_returns_bounded_page_text(self):
        body = b'<html><head><style>.x{color:red}</style></head><body><h1>Interview tips</h1><p>' + b'A' * 90000 + b'</p></body></html>'
        with patch('agent_web.requests.get', return_value=page(body, **{'content-type': 'text/html; charset=utf-8'})):
            result = agent_web.fetch('https://example.com/tips', characters=500)
        self.assertTrue(result['ok'])
        self.assertTrue(result['truncated'])
        self.assertIn('Interview tips', result['text'])
        self.assertNotIn('color:red', result['text'])
        self.assertLessEqual(len(result['text']), 500)

    def test_declared_charset_is_used_instead_of_assuming_utf8(self):
        body = '<html><body>café résumé</body></html>'.encode('windows-1252')
        with patch('agent_web.requests.get', return_value=page(body, **{'content-type': 'text/html; charset=windows-1252'})):
            self.assertIn('café résumé', agent_web.fetch('https://example.com/menu')['text'])

    def test_redirects_are_revalidated_before_following(self):
        first = Mock(status_code=302, headers={'location': 'http://127.0.0.1/agent'})
        with patch('agent_web.requests.get', return_value=first):
            with self.assertRaises(ValueError):
                agent_web.fetch('https://example.com/jump')

    def test_relative_redirects_are_resolved_against_the_current_url(self):
        with patch('agent_web.requests.get', side_effect=[
                Mock(status_code=302, headers={'location': '/next'}), page()]) as get:
            result = agent_web.fetch('https://example.com/jump')
        self.assertEqual([call.args[0] for call in get.call_args_list], ['https://example.com/jump', 'https://example.com/next'])
        self.assertEqual(result['url'], 'https://example.com/next')

    def test_a_redirect_loop_and_a_location_less_redirect_are_both_refused(self):
        looping = Mock(status_code=302, headers={'location': '/again'})
        with patch('agent_web.requests.get', return_value=looping):
            with self.assertRaisesRegex(ValueError, 'too many times'):
                agent_web.fetch('https://example.com/jump')
        blank = Mock(status_code=302, headers={})
        with patch('agent_web.requests.get', return_value=blank):
            with self.assertRaisesRegex(ValueError, 'no destination'):
                agent_web.fetch('https://example.com/jump')

    def test_a_second_dns_answer_cannot_move_the_connection_to_loopback(self):
        """The guard is re-applied to the answer used at connect time, not only the first one."""
        mixed = [(2, 1, 0, '', ('127.0.0.1', 443)), (2, 1, 0, '', ('93.184.216.34', 443))]
        with patch.object(agent_web.socket, 'getaddrinfo', side_effect=[mixed]):
            with agent_web._pinned('example.com'):
                self.assertEqual([item[4] for item in socket.getaddrinfo('example.com', 443)],
                                 [('93.184.216.34', 443)])
        rebound = [(2, 1, 0, '', ('169.254.169.254', 443))]
        with patch.object(agent_web.socket, 'getaddrinfo', side_effect=[rebound]):
            with agent_web._pinned('example.com'):
                with self.assertRaises(socket.gaierror):
                    socket.getaddrinfo('example.com', 443)
        unrelated = 'answers for some other name'
        with patch.object(agent_web.socket, 'getaddrinfo', side_effect=[unrelated]):
            with agent_web._pinned('example.com'):
                self.assertEqual(socket.getaddrinfo('example.org', 443), unrelated)

    def test_a_fetch_that_finishes_first_leaves_a_concurrent_fetch_guarded(self):
        """The resolver is process-global, so out-of-order exits must not hand the
        still-running fetch back the unfiltered resolver."""
        mixed = [(2, 1, 0, '', ('127.0.0.1', 443)), (2, 1, 0, '', ('93.184.216.34', 443))]
        first = agent_web._pinned('a.test')
        second = agent_web._pinned('b.test')
        with patch.object(agent_web.socket, 'getaddrinfo', return_value=list(mixed)):
            first.__enter__()
            second.__enter__()
            first.__exit__(None, None, None)
            self.assertEqual([item[4] for item in socket.getaddrinfo('b.test', 443)],
                             [('93.184.216.34', 443)])
            second.__exit__(None, None, None)
            self.assertEqual(socket.getaddrinfo('b.test', 443), mixed)

    def test_a_host_that_flips_to_loopback_between_checks_is_not_fetched(self):
        """Integration: the guard is installed around the call that actually connects."""

        def two_faces(host, port=None, *args, **kwargs):
            return PUBLIC if port is None else [(2, 1, 0, '', ('127.0.0.1', port))]

        def connect(url, **kwargs):
            socket.getaddrinfo('example.com', 443, type=socket.SOCK_STREAM)
            return page()

        with patch.object(agent_web.socket, 'getaddrinfo', side_effect=two_faces), \
                patch('agent_web.requests.get', side_effect=connect):
            with self.assertRaises(socket.gaierror):
                agent_web.fetch('https://example.com/')

    def test_error_pages_are_reported_with_their_status(self):
        with patch('agent_web.requests.get', return_value=page(status=404)):
            with self.assertRaisesRegex(ValueError, 'HTTP 404'):
                agent_web.fetch('https://example.com/gone')

    def test_body_reading_is_capped_in_size_and_in_time(self):
        consumed = []

        def stream(*args, **kwargs):
            for _ in range(400):
                consumed.append(1)
                yield b'x' * 65536

        item = Mock()
        item.raw.stream = Mock(side_effect=stream)
        self.assertEqual(len(agent_web._body(item, time.monotonic() + 30)), agent_web.MAX_BODY)
        self.assertLess(len(consumed), 400)

        slow = Mock()
        slow.raw.stream = Mock(side_effect=stream)
        with patch('agent_web.time.monotonic', return_value=10_000):
            with self.assertRaisesRegex(ValueError, 'too long'):
                agent_web._body(slow, 5)

    def test_a_script_only_page_is_not_passed_off_as_content(self):
        with patch('agent_web.requests.get', return_value=page(b'<html><body><script>x=1</script></body></html>')):
            with self.assertRaisesRegex(ValueError, 'no readable text'):
                agent_web.fetch('https://example.com/app')
