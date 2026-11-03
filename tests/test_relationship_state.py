"""Conversation pacing state: derived numbers, no stored text, and no claim of a feeling."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import relationship_state
from llm import LLM
from relationship_state import Relationship, default_path

DAY = 86400.0


class RelationshipTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'relationship-state.json'
        self.state = Relationship(self.path)

    def push(self, count, text='set the volume to forty percent'):
        for _ in range(count):
            self.state.observe(text)

    def axes(self, days_later=0.0):
        return self.state.axes(now=time.time() + days_later * DAY)

    # ── what is kept ────────────────────────────────────────────

    def test_the_message_itself_is_never_written_to_the_file(self):
        self.state.observe('My passport number is X1234567 and I am shy about it.')
        saved = json.dumps(json.loads(self.path.read_text(encoding='utf-8')))
        self.assertNotIn('passport', saved)
        self.assertNotIn('X1234567', saved)
        self.assertFalse(self.state.report()['stored_text'])

    def test_only_counters_timestamps_and_three_numbers_are_kept(self):
        self.push(4)
        self.assertEqual(sorted(json.loads(self.path.read_text(encoding='utf-8'))),
                         sorted(relationship_state.DEFAULT))

    def test_a_corrupt_file_falls_back_to_a_clean_state_instead_of_raising(self):
        self.path.write_text('{ this is not json', encoding='utf-8')
        self.assertEqual(Relationship(self.path).axes()['turns'], 0)

    def test_the_counts_survive_reopening_the_app(self):
        self.push(3)
        self.assertEqual(Relationship(self.path).axes()['turns'], 3)

    # ── familiarity ─────────────────────────────────────────────

    def test_the_stage_comes_from_messages_still_counted(self):
        self.assertEqual(self.state.stage(9), ('new', 'New here'))
        self.assertEqual(self.state.stage(10), ('regular', 'Regular'))
        self.assertEqual(self.state.stage(60), ('comfortable', 'Comfortable'))
        self.assertEqual(self.state.stage(200), ('longstanding', 'Long-standing'))

    def test_the_report_labels_the_stage_it_counted(self):
        self.push(12)
        report = self.state.report()
        self.assertEqual((report['stage'], report['turns']), ('regular', 12))
        self.push(200)
        self.assertEqual(self.state.report()['stage_label'], 'Long-standing')

    def test_years_of_silence_come_back_to_new_here(self):
        self.push(210)
        self.assertEqual(self.state.report()['stage'], 'longstanding')
        later = time.time() + 900 * DAY
        self.assertEqual(self.state.report(now=later)['stage'], 'new')
        self.assertLess(self.axes(days_later=900)['familiarity'], 0.05)

    def test_a_sitting_is_counted_by_the_gap_before_a_message(self):
        self.push(2)
        self.assertEqual(self.axes()['sessions'], 1)
        self.state.observe('still here')
        self.assertEqual(self.axes()['sessions'], 1, 'back-to-back messages are one sitting')
        self.assertEqual(self.axes()['idle_days'], 0.0)

    # ── tone, and the false-coldness guard ──────────────────────

    def test_an_ordinary_technical_question_moves_no_tone_signal(self):
        # The reason the word lists are narrow: a terse request must never read as coldness.
        self.push(5, 'what is my disk space')
        axes = self.axes()
        self.assertEqual((axes['warmth'], axes['boundary']), (0.0, 0.0))
        self.assertEqual(axes['signals'], {'warm_up': 0, 'warm_down': 0, 'boundary': 0})

    def test_thanking_raises_warmth_and_calling_an_answer_useless_lowers_it(self):
        self.state.observe('thanks, that was really helpful')
        self.assertGreater(self.axes()['warmth'], 0.15)
        colder = Relationship(Path(self.folder.name) / 'colder.json')
        colder.observe('that is useless and stupid')
        self.assertLess(colder.axes()['warmth'], -0.15)

    def test_a_tone_word_inside_another_word_does_not_count(self):
        # 'ty' and 'wow' are whole-word matches only, so a path or identifier cannot flatter itself.
        self.state.observe('open the style_ty_wow folder')
        self.assertEqual(self.axes()['signals']['warm_up'], 0)

    def test_a_bad_exchange_fades_to_neutral_instead_of_holding_a_grudge(self):
        self.push(3, 'what is the time')
        self.state.observe('that is rubbish and pointless')
        self.assertLess(self.axes()['warmth'], -0.15)
        self.assertIn('keep it courteous, brief and businesslike', self.state.state_block())
        self.assertAlmostEqual(self.axes(days_later=30)['warmth'], 0.0, places=3)
        self.assertIn('no adjustment needed', self.state.state_block(now=time.time() + 30 * DAY))

    def test_a_boundary_statement_asks_for_plain_answers_for_a_while(self):
        self.push(4, 'turn the volume down')
        self.state.observe('stop joking like that')
        self.assertGreaterEqual(self.axes()['boundary'], 0.45)
        self.assertIn('answer plainly, with no jokes or teasing', self.state.state_block())
        self.assertNotIn('plainly', self.state.state_block(now=time.time() + 30 * DAY))

    # ── the text the model is given ─────────────────────────────

    def test_no_block_is_given_for_the_first_two_messages(self):
        self.push(2)
        self.assertEqual(self.state.state_block(), '')
        self.state.observe('and a third one')
        self.assertIn('App-supplied conversation bookkeeping', self.state.state_block())

    def test_the_block_names_itself_as_data_and_forbids_a_claim_of_feeling(self):
        self.push(6)
        block = self.state.state_block()
        self.assertIn('not your own state and not your feelings', block)
        self.assertIn('never act hurt, jealous or abandoned', block)
        self.assertIn('never read this line out', block)
        for phrase in ('I feel', 'I love you', 'my friend', 'I miss you'):
            self.assertNotIn(phrase, block)

    def test_the_block_reports_the_counts_it_was_derived_from(self):
        self.push(5, 'how are the files')
        block = self.state.state_block()
        self.assertIn('5 messages over', block)
        self.assertIn('New here', block)
        self.assertIn('1 sitting', block)

    def test_neutral_tone_says_so_instead_of_inventing_a_mood(self):
        self.push(6, 'list the downloads folder')
        self.assertIn('no adjustment needed', self.state.state_block())

    # ── the switch ──────────────────────────────────────────────

    def test_turning_it_off_stops_the_block_without_deleting_the_numbers(self):
        self.push(8)
        self.assertFalse(self.state.configure(False)['enabled'])
        self.assertEqual(self.state.state_block(), '')
        self.assertEqual(self.state.observe('thanks'), {'enabled': False})
        self.assertEqual(self.axes()['signals']['warm_up'], 0, 'no signal is counted while off')
        self.assertTrue(self.state.configure(True)['enabled'])
        self.assertGreater(self.axes()['turns'], 0, 'the earlier counts are still there')

    def test_a_non_boolean_switch_is_refused(self):
        with self.assertRaises(ValueError):
            self.state.configure('yes')

    def test_the_state_file_lives_beside_the_other_local_profile_files(self):
        path = default_path(Path('X:/app/desktop-profile'))
        self.assertTrue(path.endswith('relationship-state.json'))
        self.assertIn('desktop-profile', path)


class CompanionPacingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def new_llm(self):
        return LLM(self.root / 'conversation-memory.json', persist_memory=False)

    def chat(self, llm, text):
        """One turn that is guaranteed to reach the model, so the test is about the prompt."""
        sent = []

        def capture(messages, *args, **kwargs):
            sent.extend(messages)
            return 'Okay.'

        llm.web_search_enabled = False
        with patch.object(llm, '_request', capture), \
                patch('response_evidence.retrieve', return_value=None), \
                patch('response_evidence.response_answer', return_value=None):
            self.assertEqual(llm.chat(text), 'Okay.')
        return [message['content'] for message in sent
                if message['content'].startswith('App-supplied conversation bookkeeping')]

    def test_an_untouched_llm_sends_no_pacing_line_and_reports_off(self):
        llm = self.new_llm()
        self.assertIsNone(llm.relationship)
        self.assertEqual(self.chat(llm, 'hello there'), [])
        report = llm.relationship_report()
        self.assertFalse(report['enabled'])
        self.assertEqual(report['turns'], 0)

    def test_the_pacing_line_reaches_the_prompt_only_after_a_few_turns(self):
        llm = self.new_llm()
        llm.configure_relationship(True, self.root / 'pace.json')
        self.assertEqual(self.chat(llm, 'tell me about the first'), [])
        self.assertEqual(self.chat(llm, 'tell me about the second'), [])
        blocks = self.chat(llm, 'tell me about the third')
        self.assertEqual(len(blocks), 1)
        self.assertIn('3 messages over', blocks[0])
        self.assertEqual(len(self.chat(llm, 'tell me about the fourth')), 1)

    def test_a_warm_exchange_and_a_boundary_exchange_produce_different_lines(self):
        warm = self.new_llm()
        warm.configure_relationship(True, self.root / 'warm.json')
        for _ in range(3):
            self.chat(warm, 'thanks, helpful as ever')
        self.assertIn('a warm, relaxed tone fits', warm.relationship.state_block())
        firm = self.new_llm()
        firm.configure_relationship(True, self.root / 'firm.json')
        for _ in range(3):
            self.chat(firm, 'stop joking like that')
        self.assertIn('answer plainly', firm.relationship.state_block())

    def test_turning_the_switch_off_leaves_the_line_out_of_the_prompt(self):
        llm = self.new_llm()
        llm.configure_relationship(True, self.root / 'off.json')
        for _ in range(4):
            self.chat(llm, 'how about now')
        self.assertTrue(self.chat(llm, 'and now'))
        llm.configure_relationship(False, self.root / 'off.json')
        self.assertEqual(self.chat(llm, 'and now again'), [])
        self.assertEqual(llm.relationship_report()['turns'], 5, 'the counts are kept, not erased')

    def test_a_state_file_that_cannot_be_written_does_not_break_a_reply(self):
        llm = self.new_llm()
        llm.configure_relationship(True, self.root / 'broken.json')
        broken = Mock()
        broken.observe = Mock(side_effect=OSError('disk full'))
        broken.state_block = Mock(side_effect=OSError('unreadable'))
        llm.relationship = broken
        self.assertEqual(self.chat(llm, 'anything at all'), [])


class SettingsApiTests(unittest.TestCase):
    """The switch and the readout have to behave like every other setting: validated, applied, local."""

    def request(self, path='/api/settings', method='POST', client='127.0.0.1'):
        import app
        from starlette.requests import Request
        origin = 'http://' + client + ':' + str(app.gui_server.port)
        return Request({'type': 'http', 'method': method, 'scheme': 'http', 'path': path,
                        'query_string': b'', 'headers': [(b'host', origin.split('://')[1].encode()),
                        (b'origin', origin.encode())], 'client': (client, 1234),
                        'server': ('127.0.0.1', app.gui_server.port)})

    def test_a_non_boolean_switch_is_rejected_before_anything_is_saved(self):
        import app, asyncio
        model = Mock()
        with patch.object(app, 'llm', model), patch.object(app, 'save_settings', return_value={}) as save:
            result = asyncio.run(app.update_app_settings(self.request(), {'relationship_adaptation': 'surely'}))
            self.assertEqual(result.status_code, 400)
            save.assert_not_called()

    def test_the_switch_reaches_the_reply_path_and_comes_back_in_the_response(self):
        import app, asyncio
        model = Mock()
        model.configure_relationship.return_value = {'ok': True, 'enabled': False, 'turns': 4}
        with patch.object(app, 'llm', model), patch.object(app, 'save_settings', return_value={}) as save:
            result = asyncio.run(app.update_app_settings(self.request(), {'relationship_adaptation': False}))
        self.assertFalse(save.call_args.args[0]['relationship_adaptation'])
        model.configure_relationship.assert_called_once_with(False)
        self.assertFalse(result['relationship_adaptation']['enabled'])
        self.assertEqual(result['relationship_adaptation']['turns'], 4, 'the counts stay where they are')

    def test_the_readout_answers_this_computer_and_refuses_another(self):
        import app, asyncio
        model = Mock()
        model.relationship_report.return_value = {'ok': True, 'enabled': True, 'turns': 12}
        with patch.object(app, 'llm', model):
            here = asyncio.run(app.relationship_status(self.request(client='127.0.0.1')))
            self.assertEqual(here['turns'], 12)
            refused = asyncio.run(app.relationship_status(self.request(client='10.1.2.3')))
            self.assertEqual(refused.status_code, 403)

    def test_the_readout_is_not_offered_in_tracking_only_mode(self):
        import app, asyncio
        with patch.object(app, 'llm', None):
            self.assertEqual(asyncio.run(app.relationship_status(self.request())).status_code, 409)


if __name__ == '__main__':
    unittest.main()
