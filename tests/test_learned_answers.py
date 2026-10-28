import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

from learned_answers import LearnedAnswers
from response_evidence import Evidence
from search_confirmation import SearchConsent


def sourced():
    url='https://en.wikipedia.org/?curid=123'
    return Evidence('A compiler translates source code.\nSource: '+url,'Verified',.9,[{'url':url,'kind':'external','title':'Reference'}],'reference retrieval')


class LearnedAnswerTests(unittest.TestCase):
    def test_approved_search_reads_general_source_when_dedicated_lookup_has_no_answer(self):
        from learned_answers import learn_approved_search
        found={'title':'Reference','text':'A readable public explanation.',
               'url':'https://example.org/reference'}
        with patch('learned_answers.learned_answers.learn',return_value=None),patch('agent_web.lookup',return_value=found) as lookup:
            reply=learn_approved_search('How does an induction motor work?',('key','model',''))
        lookup.assert_called_once_with('How does an induction motor work?',('key','model',''),characters=1800)
        self.assertIn(found['text'],reply)
        self.assertIn(found['url'],reply)
        self.assertIn('not saved',reply)

    def test_approved_gpu_search_reads_source_and_remembers_paraphrased_question(self):
        page='<table><tr><th></th><th>GeForce RTX 5060 Ti</th><th>GeForce RTX 5060</th></tr><tr><td>Standard Memory Config</td><td>16 GB / 8 GB GDDR7</td><td>8 GB GDDR7</td></tr></table>'
        import factual_grounding
        factual_grounding._cache.clear()
        with tempfile.TemporaryDirectory() as folder:
            cache=LearnedAnswers(Path(folder)/'learned.json')
            with patch('factual_grounding.requests.get',return_value=Mock(content=page.encode(),text=page)) as read:
                learned=cache.learn('rtx 5060 has how much vram')
            self.assertIsNotNone(learned);self.assertIn('8 GB',learned.text)
            read.assert_called_once()
            with patch('factual_grounding.requests.get') as read:
                recalled=LearnedAnswers(cache.path).recall('Does RTX 5060 have 24GB of VRAM?')
            self.assertIn('RTX 5060 with 8 GB',recalled.text);read.assert_not_called()

    def test_verified_answer_survives_reopen_and_needs_no_retrieval_next_time(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'learned.json';cache=LearnedAnswers(path)
            with patch('learned_answers.retrieve',return_value=sourced()) as retrieve:
                self.assertIsNotNone(cache.learn('What is a compiler?'))
                retrieve.assert_called_once_with('What is a compiler?',{},allow_actions=False)
            with patch('learned_answers.retrieve') as retrieve:
                answer=LearnedAnswers(path).recall('what is a compiler')
            self.assertEqual(answer.text,sourced().text);retrieve.assert_not_called()

    def test_guesses_unknowns_and_unsourced_claims_are_never_learned(self):
        with tempfile.TemporaryDirectory() as folder:
            cache=LearnedAnswers(Path(folder)/'learned.json')
            for value in (None,Evidence('Guess','Inference',1),Evidence('Guess','Verified',1),Evidence('Unknown')):
                with patch('learned_answers.retrieve',return_value=value):
                    self.assertIsNone(cache.learn('What is a compiler?'))
            self.assertFalse(cache.path.exists())

    def test_live_information_is_not_frozen_and_old_cache_expires(self):
        with tempfile.TemporaryDirectory() as folder:
            cache=LearnedAnswers(Path(folder)/'learned.json')
            with patch('learned_answers.retrieve') as retrieve:
                for question in ('current weather Mumbai','latest news','CPU usage','stock price today'):
                    self.assertIsNone(cache.learn(question))
                retrieve.assert_not_called()
            with patch('learned_answers.retrieve',return_value=sourced()),patch('learned_answers.time.time',return_value=100):cache.learn('What is a compiler?')
            with patch('learned_answers.time.time',return_value=100+31*86400):self.assertIsNone(cache.recall('What is a compiler?'))

    def test_learning_only_follows_an_approved_successful_browser_open(self):
        learn=Mock(return_value=' Saved verified information.')
        consent=SearchConsent(on_approved=learn)
        consent.offer('What is a compiler?',"I don't know.")
        learn.assert_not_called()
        with patch('search_confirmation.open_google_in_chrome',return_value='Opening Google in Chrome to search your question.'):
            self.assertIn('Saved verified information',consent.respond('yes'))
        learn.assert_called_once_with('What is a compiler?')
        learn.reset_mock();consent.offer('What is a compiler?',"I don't know.")
        consent.respond('no');learn.assert_not_called()


class LearnedEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_recall_answers_without_model_or_browser(self):
        import app as server
        model=Mock()
        with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={'response_restriction_level':'off'}),patch('learned_answers.learned_answers.recall',return_value=sourced()),patch('search_confirmation.search_consent.respond',return_value=None),patch('assistant_commands.run_command') as command,patch('search_confirmation.open_google_in_chrome') as browser:
            result=await server.chat({'text':'What is a compiler?','defer_audio':True})
        self.assertEqual(result['reply'],sourced().text)
        self.assertTrue(result['learned_answer']);self.assertEqual(result['sources'],sourced().sources)
        model.chat.assert_not_called();command.assert_not_called();browser.assert_not_called()
