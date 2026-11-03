"""An expression said indirectly still has to reach the viewer, and only when the sentence was about one."""
import unittest
from unittest.mock import Mock, patch

import app as server
from assistant_tools import classify, execute
from avatar_expression_command import request, request_from_speech


class GrammarTests(unittest.TestCase):
    def test_the_label_drops_the_words_that_only_hold_the_sentence_together(self):
        for said, wanted in [('show happy expression', 'happy'), ('show me the blush expression', 'blush'),
                             ('switch to sad face', 'sad'), ('show happy eyes expression', 'happy eyes'),
                             ('use my weekly-report preset', 'weekly-report')]:
            with self.subTest(said):
                self.assertEqual(request(said), {'clear': False, 'label': wanted})

    def test_a_description_is_not_mistaken_for_an_expression_name(self):
        for sentence in ['set volume to 50 and show happy face', 'open notepad then show blush expression',
                         'change the brightness to 40 and use the sad look']:
            with self.subTest(sentence):
                self.assertIsNone(request(sentence))

    def test_clearing_all_expressions_is_its_own_answer(self):
        self.assertEqual(request('reset expressions'), {'clear': True, 'label': 'neutral'})
        self.assertEqual(request('neutral face'), {'clear': True, 'label': 'neutral'})

    def test_a_sentence_that_is_not_about_an_expression_is_left_alone(self):
        for other in ['what is my volume', 'set volume to 50', 'show me the photos folder',
                      'open notepad', 'change the brightness to 40', '']:
            with self.subTest(other):
                self.assertIsNone(request(other))


class SpokenFormTests(unittest.TestCase):
    def test_polite_preambles_still_ask_for_the_same_expression(self):
        cases = {'can you show a happy expression': 'happy',
                 'Sakura, please switch to the blush face': 'blush',
                 'could you set the sad expression please': 'sad'}
        for said, label in cases.items():
            with self.subTest(said):
                self.assertEqual(request_from_speech(said, 'Sakura'), {'clear': False, 'label': label})

    def test_a_sequence_is_not_read_as_one_expression_request(self):
        for sentence in ['open notepad then show blush expression', 'set volume to 50 and show happy face',
                         'what can you do']:
            with self.subTest(sentence):
                self.assertIsNone(request_from_speech(sentence, 'Sakura'))


class ChatRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_the_route_hands_the_expression_to_the_viewer_before_any_command_table(self):
        model = Mock()
        with patch.object(server, 'llm', model), \
                patch.object(server, 'get_settings', return_value={'assistant_name': 'Sakura'}), \
                patch('assistant_tools.execute', side_effect=AssertionError('the chat command path ran')):
            for said, label in [('show happy expression', 'happy'), ('can you show a happy expression', 'happy')]:
                with self.subTest(said):
                    result = await server.chat({'text': said, 'defer_audio': True})
                    self.assertEqual(result['avatar_expression'], {'clear': False, 'label': label})
                    self.assertIn(label, result['reply'])
                    self.assertEqual(result['response_kind'], 'action')
        model.chat.assert_not_called()


class SequenceFallbackTests(unittest.TestCase):
    def test_classify_still_names_the_action_so_the_capability_table_stays_honest(self):
        self.assertEqual(classify('show blush expression'), ('expression.change', {'clear': False, 'label': 'blush'}))

    def test_a_step_of_a_sequence_says_why_it_could_not_be_applied(self):
        result = execute('expression.change', {'clear': False, 'label': 'blush'})
        self.assertFalse(result['ok'])
        self.assertIn('sequence', result['reply'])


if __name__ == '__main__':
    unittest.main()
