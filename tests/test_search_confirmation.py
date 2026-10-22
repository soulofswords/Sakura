import unittest
from unittest.mock import Mock,patch
from urllib.parse import parse_qs,urlparse

from search_confirmation import SearchConsent,open_google_in_chrome

UNKNOWN='I do not have a verified memory specification for that GPU here. Please share its manufacturer specification page; I should not guess the VRAM.'
QUESTION='does rtx 4080ti has 24GB vram ?'


class SearchConsentTests(unittest.TestCase):
    def test_offer_is_not_a_browser_action(self):
        consent=SearchConsent()
        with patch('search_confirmation.open_google_in_chrome') as open_browser:
            self.assertEqual(consent.offer(QUESTION,UNKNOWN),"I don't have this information. May I Google it?")
        open_browser.assert_not_called()

    def test_only_affirmation_consumes_exact_question_once(self):
        for answer in ('yes','yes u can','yes you can','yes, you can','yes please','go ahead','हाँ'):
            consent=SearchConsent();consent.offer(QUESTION,UNKNOWN)
            with patch('search_confirmation.open_google_in_chrome',return_value='Opening Google.') as open_browser:
                result=consent.respond(answer)
                self.assertEqual(result,'Opening Google.')
                open_browser.assert_called_once_with(QUESTION)
                self.assertIsNone(consent.respond('yes'))

    def test_no_unrelated_message_or_expired_offer_can_open_browser(self):
        for text in ('no','not now','maybe','tell me the time'):
            consent=SearchConsent();consent.offer(QUESTION,UNKNOWN)
            with patch('search_confirmation.open_google_in_chrome') as open_browser:
                consent.respond(text);consent.respond('yes')
            open_browser.assert_not_called()
        consent=SearchConsent();consent.offer(QUESTION,UNKNOWN)
        with patch('search_confirmation.time.monotonic',return_value=consent.pending[1]+121),patch('search_confirmation.open_google_in_chrome') as open_browser:
            self.assertIsNone(consent.respond('yes'))
        open_browser.assert_not_called()

    def test_google_query_is_encoded_exactly_and_does_not_use_shell(self):
        query='Does RTX 4080 Ti have 24GB? & echo test'
        with patch('search_confirmation.Path.is_file',return_value=True),patch('search_confirmation.subprocess.Popen') as launch:
            result=open_google_in_chrome(query)
        self.assertIn('Opening Google in Chrome',result)
        args=launch.call_args.args[0]
        self.assertIn('chrome.exe',args[0])
        self.assertEqual(parse_qs(urlparse(args[-1]).query)['q'],[query])
        self.assertFalse(launch.call_args.kwargs['shell'])


class SearchConsentEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_then_yes_in_local_and_cloud(self):
        import app as server
        for provider in ('local','gemini','openai'):
            consent=SearchConsent();model=Mock();model.reply_language='English'
            with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={'response_restriction_level':'off','llm_provider':provider}),patch('search_confirmation.search_consent',consent),patch('assistant_commands.run_command',return_value=None),patch('factual_grounding.gpu_memory_lookup',return_value=UNKNOWN),patch('search_confirmation.open_google_in_chrome',return_value='Opening Google in Chrome to search your question.') as open_browser:
                first=await server.chat({'text':QUESTION,'defer_audio':True})
                self.assertIn('May I Google it?',first['reply'])
                self.assertEqual(first['speech_reply'],first['reply'])
                open_browser.assert_not_called()
                second=await server.chat({'text':'yes you can','defer_audio':True})
                self.assertIn('Opening Google in Chrome',second['reply'])
                open_browser.assert_called_once_with(QUESTION)
                model.chat.assert_not_called()


if __name__=='__main__':unittest.main()
