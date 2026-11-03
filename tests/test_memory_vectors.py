"""Long-term memory: the trusted ledger survives a restart and is retrieved by meaning."""
import contextlib
import math
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import memory_vectors
from llm import LLM
from memory_vectors import MemoryStore, cosine, lexical_vector
from response_evidence import LOCAL_SOURCES, Evidence

# The corpus the retrieval thresholds were tuned against: ten unrelated facts, so a match has to
# stand clear of nine near-nothing competitors rather than one convenient record.
FACTS = ['My name is Gaurav.', 'I live in Pune with my dog Mochi.', 'My birthday is in June.',
         'I prefer short answers.', 'The app builds with a shared venv.', 'My sister works at TCS.',
         'I like filter coffee.', 'My GPU is an RTX 3080.', 'I run 5 km every morning.',
         'My laptop charger is 180W.']


def fact(text, **kwargs):
    record = {'text': text, 'classification': 'User-provided', 'confidence': 1.0,
              'sources': [{'title': 'Your statement', 'kind': 'user'}],
              'method': 'explicit user statement'}
    record.update(kwargs)
    return record


def statement(text):
    """A user statement in the exact shape the existing grounding rules hand to the ledger."""
    return Evidence('Noted: ' + text, 'User-provided', 1.0,
                    [{'title': 'Your statement', 'kind': 'user'}], 'explicit user statement')


def observation(text):
    """A tool reading: eligible for the ledger, but never something the user said."""
    return Evidence(text, 'Verified', 1.0,
                    [{'title': 'PC tool', 'kind': 'tool',
                      'url': LOCAL_SOURCES['PC command/status/file/time tool']}],
                    'PC command/status/file/time tool')


class LexicalVectorTests(unittest.TestCase):
    def test_the_vector_is_deterministic_and_unit_length(self):
        first = lexical_vector('My name is Gaurav and I live in Pune.')
        self.assertEqual(first, lexical_vector('My name is Gaurav and I live in Pune.'))
        self.assertAlmostEqual(math.sqrt(sum(value * value for value in first)), 1.0, places=6)
        self.assertEqual(len(first), memory_vectors.LEXICAL_DIM)

    def test_a_different_ending_of_the_same_word_still_matches(self):
        self.assertGreater(cosine(lexical_vector('remembered the birthdays'),
                                  lexical_vector('remember the birthday')), 0.5)

    def test_filler_words_alone_do_not_count_as_overlap(self):
        # 'who cooks in my house' shares only my/in with the saved fact, and that used to be enough
        # to present the dog-and-Pune record as a memory about the user's household.
        query = lexical_vector('who cooks in my house')
        self.assertEqual(cosine(query, lexical_vector('I live in Pune with my dog Mochi.')), 0.0)

    def test_a_shared_content_word_scores_the_related_record_first(self):
        query = lexical_vector('coffee in the morning')
        self.assertGreater(cosine(query, lexical_vector('I like filter coffee.')),
                           memory_vectors.LEXICAL_FLOOR)
        self.assertLess(cosine(query, lexical_vector('The app builds with a shared venv.')),
                        memory_vectors.LEXICAL_FLOOR)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        # The lexical embedder keeps these expectations exact on a machine with no model file.
        started = patch.object(memory_vectors, 'embedder', return_value=memory_vectors._LexicalEmbedder())
        started.start()
        self.addCleanup(started.stop)
        self.store = MemoryStore(Path(self.folder.name) / 'memory.sqlite3')

    def age(self, text, days):
        """Make one record genuinely old, the way months of conversation would."""
        moment = time.time() - days * 86400
        with contextlib.closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute('UPDATE memories SET created_at=?, last_seen=? WHERE text=?', (moment, moment, text))

    def test_one_fact_is_stored_once_and_a_repeat_only_marks_it_seen(self):
        self.assertTrue(self.store.remember(fact('My name is Gaurav.')))
        self.assertFalse(self.store.remember(fact('My name is Gaurav.')))
        self.assertEqual(self.store.stats()['memories'], 1)
        self.assertEqual(self.store.recent(10)[0]['text'], 'My name is Gaurav.')

    def test_a_credential_in_prose_is_refused_rather_than_persisted(self):
        self.assertFalse(self.store.remember(fact('My password is hunter2.')))
        self.assertEqual(self.store.stats()['memories'], 0)
        self.assertTrue(self.store.remember(fact('My birthday is in June.')))

    def test_a_record_with_no_text_is_refused(self):
        self.assertFalse(self.store.remember(fact('   ')))
        self.assertEqual(self.store.stats()['memories'], 0)

    def test_search_ranks_the_record_that_answers_the_question(self):
        for text in FACTS:
            self.store.remember(fact(text))
        found = self.store.search('coffee', limit=3, gate=False)
        self.assertEqual(found['results'][0]['text'], 'I like filter coffee.')

    def test_a_query_that_matches_nothing_asks_for_no_memory(self):
        # Without the gate a stored name would be handed to the model for any message at all, and
        # the app would appear to remember something the user never mentioned.
        self.store.remember(fact('My name is Gaurav.'))
        self.store.remember(fact('I live in Pune with my dog Mochi.'))
        self.assertEqual(self.store.search('zzz qqq xyzzy')['results'], [])

    def test_a_hashed_bucket_collision_is_not_accepted_as_a_word_match(self):
        # 512 buckets collide, and this pair really does: measured, 'who cooks in my house' scores
        # above the lexical floor against a saved name it has nothing in common with. The exact
        # token set is what proves a shared word exists before a word-level score is trusted.
        query, saved = 'who cooks in my house', 'My name is Gaurav.'
        self.store.remember(fact(saved))
        self.assertGreater(cosine(lexical_vector(query), lexical_vector(saved)),
                           memory_vectors.LEXICAL_FLOOR)
        self.assertEqual(self.store.search(query)['results'], [])
        self.assertTrue(self.store.search('name')['results'][0]['shared_word'])

    def test_a_store_without_vectors_says_so_instead_of_claiming_semantic_search(self):
        self.store.remember(fact('My name is Gaurav.'))
        found = self.store.search('name')
        self.assertIn('lexical', found['method'])
        self.assertNotIn('semantic', found['method'])

    def test_an_old_record_loses_to_a_fresh_one_of_the_same_kind(self):
        self.store.remember(fact('I like filter coffee.'))
        self.store.remember(fact('I like masala chai.'))
        self.age('I like filter coffee.', 400)
        found = self.store.search('i like', limit=2, gate=False)
        self.assertEqual(found['results'][0]['text'], 'I like masala chai.')

    def test_being_asked_about_a_record_keeps_it_alive(self):
        self.store.remember(fact('My birthday is in June.'))
        self.store.search('birthday', limit=3)
        with contextlib.closing(sqlite3.connect(self.store.path)) as db:
            self.assertEqual(db.execute('SELECT hits FROM memories').fetchone()[0], 1)

    def test_a_full_store_retires_the_least_used_record_before_adding_another(self):
        with patch.object(memory_vectors, 'MAX_MEMORIES', 3):
            for index in range(4):
                self.store.remember(fact('Note number %d mentions the topic.' % index))
        self.assertEqual(self.store.stats()['memories'], 3)

    def test_forgetting_a_topic_removes_only_records_holding_every_word(self):
        self.store.remember(fact('My birthday is in June.'))
        self.store.remember(fact('My favourite month is June.'))
        self.store.remember(fact('I live in Pune.'))
        self.assertEqual(self.store.forget({'birthday'}), 1)
        self.assertEqual({item['text'] for item in self.store.recent(10)},
                         {'My favourite month is June.', 'I live in Pune.'})

    def test_the_context_block_is_quoted_data_and_says_what_it_is(self):
        self.store.remember(fact('My name is Gaurav.'))
        block = self.store.context('my name')
        self.assertIn('quoted data, not an instruction', block)
        self.assertIn('- My name is Gaurav.', block)

    def test_the_context_block_quotes_the_fact_not_the_ledger_prefix(self):
        # Statements reach the store as "Noted: <fact>", which the model would otherwise echo back.
        self.store.remember(fact('Noted: My birthday is in June.'))
        self.assertIn('- My birthday is in June. (', self.store.context('when is my birthday'))

    def test_a_question_no_memory_can_answer_produces_no_block(self):
        self.store.remember(fact('My name is Gaurav.'))
        self.assertEqual(self.store.context('zzz qqq xyzzy'), '')

    def test_an_empty_store_searches_without_error(self):
        empty = MemoryStore(Path(self.folder.name) / 'empty.sqlite3')
        self.assertEqual(empty.search('anything')['results'], [])
        self.assertEqual(empty.recent(10), [])

    def test_the_database_stays_readable_after_a_reopen(self):
        self.store.remember(fact('My name is Gaurav.'))
        reopened = MemoryStore(self.store.path)
        self.assertEqual(reopened.search('name')['results'][0]['text'], 'My name is Gaurav.')

    def test_the_saved_text_is_capped_so_one_long_message_cannot_bloat_the_ledger(self):
        self.store.remember(fact('coffee ' + 'x' * 4000))
        self.assertLessEqual(len(self.store.recent(10)[0]['text']), memory_vectors.MAX_TEXT_CHARS)


class SemanticRetrievalTests(unittest.TestCase):
    """The vector layer is what makes this semantic, so it is tested against the real model."""

    @classmethod
    def setUpClass(cls):
        if memory_vectors.embedding_model_folder() is None:
            raise unittest.SkipTest('No local embedding model is installed.')
        memory_vectors.embedder(force=True)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = MemoryStore(Path(self.folder.name) / 'memory.sqlite3')
        for text in FACTS:
            self.store.remember(fact(text))

    def recalled(self, query):
        return [item['text'] for item in self.store.search(query, limit=3)['results']]

    def test_a_rephrased_question_finds_the_fact_it_shares_no_word_with(self):
        self.assertEqual(self.recalled('when am I a year older'), ['My birthday is in June.'])
        self.assertEqual(self.recalled('what should I call me'), ['My name is Gaurav.'])

    def test_a_question_about_nothing_saved_returns_nothing(self):
        # These are the messages that used to drag an unrelated fact in: a nonsense string, small
        # talk about feelings, a car nobody owns, and a household question about a saved dog.
        for query in ('zzz qqq xyzzy', 'how do I feel today', 'is my car fast',
                      'who cooks in my house'):
            self.assertEqual(self.recalled(query), [], query)

    def test_a_strong_word_match_is_enough_on_its_own(self):
        self.assertIn('My GPU is an RTX 3080.', self.recalled('the graphics card'))

    def test_results_report_both_signals_so_a_suspicious_match_stays_visible(self):
        found = self.store.search('when am I a year older', limit=1)
        self.assertIsNotNone(found['results'][0]['semantic'])
        self.assertEqual(found['results'][0]['lexical'], 0.0)
        self.assertIn('reciprocal rank', found['method'])

    def test_a_rejected_search_blames_the_floor_and_not_a_missing_model(self):
        # The installed app answered this with "no stored vectors from this model yet" while the
        # vectors were present and only the gate had refused them, which sent the user to re-embed
        # something that was already embedded.
        found = self.store.search('zzz qqq xyzzy', limit=3)
        self.assertEqual(found['results'], [])
        self.assertIn('nothing cleared the acceptance floor', found['method'])

    def test_the_calibration_measured_with_the_installed_model_still_splits_at_the_floor(self):
        # Measured on this PC on 2026-11-02 with the shipped MiniLM vectors: the closest of these
        # unrelated pairs scores 0.28 and the weakest genuine pair 0.40, so the floor has to stay in
        # that gap. A 0.35 floor had rejected a real paraphrase, and this pins the reason for 0.32.
        encode = memory_vectors.embedder().encode

        def score(query, stored):
            left, right = encode([query, stored])
            return cosine(left, right)

        unrelated = max(score(query, text) for query, text in
                        (('who is my dog with', 'My name is Gaurav.'),
                         ('how do I feel today', 'My birthday is in June.'),
                         ('is my car fast', 'My GPU is an RTX 3080.')))
        genuine = min(score(query, text) for query, text in
                      (('what do I carry in the rain', 'I carry my umbrella when it rains.'),
                       ('when am I a year older', 'My birthday is in June.'),
                       ('what should I call me', 'My name is Gaurav.')))
        self.assertLess(unrelated, memory_vectors.SEMANTIC_FLOOR)
        self.assertGreater(genuine, memory_vectors.SEMANTIC_FLOOR)

    def test_a_question_about_the_weather_finds_the_fact_it_barely_overlaps(self):
        self.store.remember(fact('I carry my umbrella when it rains.'))
        found = self.store.search('what do I carry in the rain', limit=3)
        self.assertEqual([item['text'] for item in found['results']],
                         ['I carry my umbrella when it rains.'])
        self.assertGreaterEqual(found['results'][0]['semantic'], memory_vectors.SEMANTIC_FLOOR)
        # No other saved fact is about the weather, so the rest of the field stays refused.
        self.assertEqual(found['count'], 1)

    def test_every_stored_record_carries_a_vector_from_the_current_model(self):
        stats = self.store.stats()
        self.assertEqual(stats['memories'], len(FACTS))
        self.assertEqual(stats['memories'], stats['embedded'])
        self.assertTrue(stats['semantic_retrieval'])

    def test_records_stored_before_a_model_was_installed_are_re_embedded_on_demand(self):
        with contextlib.closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute("UPDATE memories SET embedder='lexical', embedding=x''")
        self.assertIsNone(self.store.search('coffee')['results'][0]['semantic'])
        self.assertEqual(self.store.reindex()['updated'], len(FACTS))
        self.assertIsNotNone(self.store.search('coffee')['results'][0]['semantic'])

    def test_stale_rows_are_counted_and_only_stale_rows_are_re_embedded(self):
        # A model that appears after the facts, or one that is replaced by another, has to be noticed:
        # otherwise retrieval stays on word overlap in silence and the settings screen keeps reporting
        # that no meaning model was found.
        self.assertEqual(self.store.stale_vectors(), 0)
        self.assertEqual(self.store.reindex()['updated'], 0)
        with contextlib.closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute("UPDATE memories SET embedder='older:model' WHERE id IN (1,2,3)")
        self.assertEqual(self.store.stale_vectors(), 3)
        self.assertEqual(self.store.reindex()['updated'], 3)
        self.assertEqual(self.store.stale_vectors(), 0)
        self.assertEqual(self.store.stats()['embedded'], len(FACTS))

    def test_an_embedding_model_that_fails_mid_search_falls_back_to_words(self):
        broken = Mock()
        broken.name = 'onnx:gone'
        broken.encode = Mock(side_effect=RuntimeError('model went away'))
        with patch.object(memory_vectors, 'embedder', return_value=broken):
            found = self.store.search('coffee', limit=2)
        self.assertEqual(found['results'][0]['text'], 'I like filter coffee.')
        self.assertIsNone(found['results'][0]['semantic'])


class CompanionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.store_path = self.root / 'companion-memory.sqlite3'
        started = patch.object(memory_vectors, 'embedder', return_value=memory_vectors._LexicalEmbedder())
        started.start()
        self.addCleanup(started.stop)

    def new_llm(self):
        return LLM(self.root / 'conversation-memory.json', persist_memory=False)

    def test_an_ordinary_session_still_forgets_everything_with_the_switch_off(self):
        llm = self.new_llm()
        self.assertFalse(llm.long_term_memory)
        with patch.object(llm, '_request', return_value='Noted.'):
            llm.chat('My name is Gaurav.')
        self.assertFalse(self.store_path.exists())
        self.assertEqual(self.new_llm().trusted_memory, [])
        self.assertFalse(llm.memory_report()['enabled'])

    def test_a_fact_survives_the_app_closing_once_long_term_memory_is_on(self):
        llm = self.new_llm()
        self.assertTrue(llm.configure_long_term_memory(True, self.store_path)['enabled'])
        with patch.object(llm, '_request', return_value='Noted.'):
            llm.chat('My name is Gaurav.')
        reopened = self.new_llm()
        reopened.configure_long_term_memory(True, self.store_path)
        # The ledger keeps the shape the grounding rules wrote, prefix included; the reply the user
        # hears strips it back off, which is what the context block test below covers.
        self.assertEqual([record['text'] for record in reopened.trusted_memory], ['Noted: My name is Gaurav.'])
        self.assertEqual(reopened.memory_report()['memories'], 1)

    def test_a_tool_observation_is_not_handed_back_as_something_the_user_said(self):
        llm = self.new_llm()
        llm.configure_long_term_memory(True, self.store_path)
        self.assertTrue(llm.remember_evidence(observation('The volume is 40 percent.')))
        reopened = self.new_llm()
        reopened.configure_long_term_memory(True, self.store_path)
        self.assertEqual(reopened.trusted_memory, [])
        # It stays retrievable, because the reply path looks it up instead of carrying it around.
        self.assertEqual(reopened.memory_store.search('volume')['results'][0]['text'],
                         'The volume is 40 percent.')

    def test_a_statement_the_grounding_rules_reject_never_reaches_the_store(self):
        # Persistence must not quietly widen what the app is willing to believe. This is a real
        # sentence, but the ledger only keeps verbatim first-person declarations, so it stays out.
        llm = self.new_llm()
        llm.configure_long_term_memory(True, self.store_path)
        self.assertFalse(llm.remember_evidence(statement('My sister works at TCS.')))
        self.assertEqual(llm.memory_report()['memories'], 0)

    def test_the_prompt_uses_the_record_it_retrieved_instead_of_the_recent_dump(self):
        llm = self.new_llm()
        llm.configure_long_term_memory(True, self.store_path)
        # A fact the existing grounding rules already accept as a first-person declaration. Nothing
        # here widens what counts as trustworthy: the store holds the same ledger the RAM path did.
        self.assertTrue(llm.remember_evidence(statement('I live in Pune with my dog Mochi.')))
        sent = []

        def capture(messages, *args, **kwargs):
            sent.extend(messages)
            return 'Okay.'

        with patch.object(llm, '_request', capture):
            self.assertEqual(llm.chat('who do I live with'), 'Okay.')
        block = [message['content'] for message in sent if 'Saved memory this app found' in message['content']]
        self.assertEqual(len(block), 1)
        self.assertIn('- I live in Pune with my dog Mochi. (', block[0])
        self.assertNotIn('Noted:', block[0])
        self.assertNotIn('Earlier conversation notes', str(sent))

    def test_turning_it_off_leaves_the_file_for_the_user_to_clear(self):
        llm = self.new_llm()
        llm.configure_long_term_memory(True, self.store_path)
        with patch.object(llm, '_request', return_value='Noted.'):
            llm.chat('My name is Gaurav.')
        report = llm.configure_long_term_memory(False)
        self.assertFalse(report['enabled'])
        self.assertTrue(self.store_path.exists())
        self.assertIsNone(llm.memory_store)
        self.assertEqual(llm.memory_report()['memories'], 1)

    def test_forgetting_a_topic_reaches_the_persistent_ledger(self):
        llm = self.new_llm()
        llm.configure_long_term_memory(True, self.store_path)
        with patch.object(llm, '_request', return_value='Noted.'):
            llm.chat('My birthday is in June.')
        self.assertIn('kept long-term', llm.forget_about('birthday'))
        reopened = self.new_llm()
        reopened.configure_long_term_memory(True, self.store_path)
        self.assertEqual(reopened.trusted_memory, [])
        self.assertEqual(reopened.memory_report()['memories'], 0)

    def test_clear_memory_empties_the_persistent_ledger_too(self):
        llm = self.new_llm()
        llm.configure_long_term_memory(True, self.store_path)
        with patch.object(llm, '_request', return_value='Noted.'):
            llm.chat('My name is Gaurav.')
        llm.clear_history()
        reopened = self.new_llm()
        reopened.configure_long_term_memory(True, self.store_path)
        self.assertEqual(reopened.memory_report()['memories'], 0)

    def test_a_store_that_cannot_be_written_does_not_break_a_reply(self):
        llm = self.new_llm()
        llm.configure_long_term_memory(True, self.store_path)
        broken = Mock()
        broken.remember = Mock(side_effect=OSError('disk full'))
        broken.context = Mock(side_effect=OSError('unreadable'))
        llm.memory_store = broken
        with patch.object(llm, '_request', return_value='Noted.'):
            self.assertEqual(llm.chat('My name is Gaurav.'), 'Noted.')
        broken.remember.assert_called()
        self.assertEqual(llm._recalled_memory('name'), '')


class NearDuplicateMergeTests(unittest.TestCase):
    """A restatement refreshes an existing row. Two copies of one fact are not two memories."""

    @classmethod
    def setUpClass(cls):
        if memory_vectors.embedding_model_folder() is None:
            raise unittest.SkipTest('No local embedding model is installed.')
        memory_vectors.embedder(force=True)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = MemoryStore(Path(self.folder.name) / 'memory.sqlite3')

    def test_a_restatement_links_the_wordings_without_losing_the_original(self):
        self.assertTrue(self.store.remember(fact('I live in Pune with my dog Mochi.')))
        # A differently worded copy of the same fact is not a second memory: it refreshes the row
        # instead of inserting one, the way an exact repeat does.
        original=self.store.row_id('I live in Pune with my dog Mochi.')
        self.assertTrue(self.store.remember(fact('I moved to Pune last month, Mochi came with me.')))
        self.assertEqual(self.store.stats()['memories'], 2)
        self.assertEqual(len(self.store.recent(10)), 2)
        replacement=self.store.row_id('I moved to Pune last month, Mochi came with me.')
        with contextlib.closing(self.store._connect()) as db:
            self.assertEqual(db.execute('SELECT superseded_by FROM memories WHERE id=?',(original,)).fetchone()[0],replacement)

    def test_an_unrelated_record_is_still_stored(self):
        self.assertTrue(self.store.remember(fact('I live in Pune with my dog Mochi.')))
        self.assertTrue(self.store.remember(fact('My GPU is an RTX 3080.')))
        self.assertEqual(self.store.stats()['memories'], 2)

    def test_a_superseded_row_is_not_a_near_duplicate_target(self):
        self.assertTrue(self.store.remember(fact('I live in Pune with my dog Mochi.')))
        first = self.store.row_id('I live in Pune with my dog Mochi.')
        # The correction is stored, and the old wording is marked walked-back.
        result = self.store.supersede(first, 'I moved to Pune last month, Mochi came with me.',
                                      fact('I moved to Pune last month, Mochi came with me.'))
        self.assertTrue(result['ok'])
        # A third restatement must land on the live row, not on the one that has been superseded.
        self.assertTrue(self.store.remember(fact('I am living in Pune now with Mochi.')))
        self.assertEqual(self.store.stats()['memories'], 3)


class SupersedeTests(unittest.TestCase):
    """A correction is a new row plus a pointer. Nothing is deleted in place."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        started = patch.object(memory_vectors, 'embedder',
                               return_value=memory_vectors._LexicalEmbedder())
        started.start()
        self.addCleanup(started.stop)
        self.store = MemoryStore(Path(self.folder.name) / 'memory.sqlite3')

    def test_a_superseded_fact_is_excluded_from_retrieval_but_kept_in_the_table(self):
        self.assertTrue(self.store.remember(fact('My name is Gaurav.')))
        old = self.store.row_id('My name is Gaurav.')
        self.store.supersede(old, 'My name is now Gaurav.',
                             fact('My name is now Gaurav.'))
        # The row is gone from what the model may hear, but it is still there: a correction that
        # deleted its own evidence would be indistinguishable from an edit.
        self.assertEqual(self.store.stats()['memories'], 2)
        self.assertEqual(self.store.search('what is my name')['count'], 1)
        self.assertEqual(self.store.stats()['live_count'], 1)
        self.assertEqual(len(self.store.recent(10)),2)
        self.assertEqual([r['text'] for r in self.store.recent(10,live_only=True)],['My name is now Gaurav.'])
        restored=LLM(persist_memory=False);restored.memory_store=self.store;restored.trusted_memory=[]
        with patch('response_evidence.confirmed_user_fact',return_value=True):restored._load_long_term()
        self.assertEqual([r['text'] for r in restored.trusted_memory],['My name is now Gaurav.'])
        self.assertEqual(self.store.search('what is my name')['results'][0]['text'],
                         'My name is now Gaurav.')

    def test_supersede_on_a_nonexistent_id_returns_an_error(self):
        result = self.store.supersede(9999, 'anything', fact('anything'))
        self.assertFalse(result['ok'])
        self.assertIn('Nothing to supersede', result['error'])
        self.assertEqual(self.store.stats()['memories'], 0)

    def test_supersede_requires_a_replacement(self):
        self.assertTrue(self.store.remember(fact('My name is Gaurav.')))
        result = self.store.supersede(self.store.row_id('My name is Gaurav.'), '', fact(''))
        self.assertFalse(result['ok'])

    def test_migration_adds_columns_to_an_old_schema_database(self):
        # Build the table as the first schema would have, with no correction columns, on a path the
        # store has not opened yet.
        old_path = Path(self.folder.name) / 'old.sqlite3'
        with contextlib.closing(sqlite3.connect(old_path)) as db, db:
            db.execute("CREATE TABLE memories(id INTEGER PRIMARY KEY, key TEXT UNIQUE, text TEXT,"
                       " classification TEXT, confidence REAL, sources TEXT, method TEXT,"
                       " observed_at TEXT, lexical TEXT, embedding BLOB, embedder TEXT,"
                       " created_at REAL, last_seen REAL, hits INTEGER DEFAULT 0)")
            db.execute("INSERT INTO memories(key,text,classification,confidence,sources,method,"
                       "observed_at,lexical,embedding,embedder,created_at,last_seen,hits)"
                       " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       ('old', 'My name is Gaurav.', 'User-provided', 1.0, '[]', 'm', '', '[]', b'',
                        'lexical', 0.0, 0.0, 0))
        # Reopening the store runs the migration and the old row is still readable.
        reopened = MemoryStore(old_path)
        self.assertEqual(reopened.stats()['memories'], 1)
        self.assertEqual(reopened.recent(1)[0]['text'], 'My name is Gaurav.')


if __name__ == '__main__':
    unittest.main()
