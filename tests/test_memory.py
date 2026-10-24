import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import requests
from llm import LLM

# 'hello' is answered by the local evidence layer, so memory tests that mean to
# exercise a provider call have to ask something that actually reaches it.
QUESTION = 'Describe the difference between a retry and a rollback.'


class MemoryTests(unittest.TestCase):
    def test_saved_memory_and_clear(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'memory.json'
            llm = LLM(path)
            with patch.object(llm, '_request', return_value='I will remember that.'):
                reply = llm.chat('My name is Gaurav and I prefer short answers.')
            # The write is silent: the user hears the model's own reply, not a receipt.
            self.assertEqual(reply, 'I will remember that.')
            self.assertEqual(llm.trusted_memory[0]['classification'], 'User-provided')
            self.assertNotIn('receipt', reply.lower())
            restored = LLM(path)
            self.assertEqual(restored.history[0]['content'], 'My name is Gaurav and I prefer short answers.')
            self.assertEqual([item['role'] for item in restored.history], ['user', 'assistant'])
            self.assertEqual(restored.trusted_memory, llm.trusted_memory)
            restored.clear_history()
            self.assertEqual(LLM(path).history, [])
            self.assertEqual(LLM(path).trusted_memory, [])

    def test_stored_fact_is_recalled_without_the_model(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'memory.json'
            llm = LLM(path)
            with patch.object(llm, '_request', return_value='Nice to meet you.'):
                llm.chat('My name is Gaurav.')
            generate = Mock(side_effect=AssertionError('recall should not ask the model'))
            with patch.object(llm, '_request', generate):
                reply = llm.chat('What is my name?')
            generate.assert_not_called()
            self.assertEqual(reply, 'You told me: My name is Gaurav.')
            # The quotation is not stored again as dialogue; only the original exchange is.
            self.assertEqual(len(LLM(path).history), 2)

    def test_a_retrieved_answer_is_recorded_as_a_turn(self):
        from response_evidence import Evidence
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'memory.json'
            llm = LLM(path)
            url = 'https://open-meteo.com/v1/forecast'
            retrieved = Evidence(f'Pune is 26 C and clear. Source: {url}', 'Verified', 1,
                                 [{'title': 'Forecast', 'kind': 'external', 'url': url}],
                                 'weather/news retrieval')
            generate = Mock(side_effect=AssertionError('a retrieved answer must not ask the model'))
            with patch('response_evidence.retrieve', return_value=retrieved), patch.object(llm, '_request', generate):
                self.assertEqual(llm.chat("What is Pune's weather?"), retrieved.text)
            generate.assert_not_called()
            self.assertEqual([item['role'] for item in LLM(path).history], ['user', 'assistant'])

    def test_dialogue_is_bounded_to_complete_exchanges(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'memory.json'
            llm = LLM(path)
            llm.history = [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': str(i)} for i in range(122)]
            llm._save_memory()
            self.assertEqual(json.loads(path.read_text())['version'], 3)
            restored = LLM(path)
            self.assertEqual(len(restored.history), 100)
            self.assertEqual(restored.history[0]['content'], '22')
            self.assertEqual(restored.history[-1]['content'], '121')

    def test_a_half_finished_exchange_is_never_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'memory.json'
            llm = LLM(path)
            llm.history = [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': str(i)} for i in range(41)]
            llm._save_memory()
            tail = json.loads(path.read_text())['history']
            self.assertEqual(len(tail) % 2, 0)
            self.assertEqual(tail[-1]['role'], 'assistant')
            self.assertEqual(tail[-1]['content'], '39')

    def test_saved_dialogue_is_context_never_verified_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'memory.json'
            hallucination = 'The RTX 5090 has 64 GB of VRAM.'
            path.write_text(json.dumps({'version': 3, 'trusted_memory': [],
                                        'history': [{'role': 'user', 'content': 'How much VRAM does the 5090 have?'},
                                                    {'role': 'assistant', 'content': hallucination},
                                                    {'role': 'user', 'content': 'Thanks'},
                                                    {'role': 'assistant', 'content': 'Anytime.'}]}))
            llm = LLM(path)
            self.assertIn(hallucination, [item['content'] for item in llm.history])
            self.assertEqual(llm.trusted_memory, [])
            self.assertEqual(llm.summary, '')
            with patch.object(llm, '_request', return_value='Let me check what I know.'):
                llm.chat(QUESTION)
            # Restored dialogue is conversation context; it never becomes a recorded fact.
            self.assertEqual(llm.trusted_memory, [])
            self.assertNotIn('64 GB', llm.summary)

    def test_pre_grounding_transcripts_are_not_restored(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'memory.json'
            for legacy in ({'history': [{'role': 'assistant', 'content': 'The RTX 5090 has 64 GB of VRAM.'}],
                            'summary': 'The RTX 5090 has 64 GB of VRAM.'},
                           {'version': 2, 'history': [{'role': 'assistant', 'content': 'The RTX 5090 has 64 GB of VRAM.'}],
                            'trusted_memory': []}):
                path.write_text(json.dumps(legacy))
                llm = LLM(path)
                self.assertEqual(llm.history, [])
                self.assertEqual(llm.trusted_memory, [])

    def test_older_turns_survive_restart_without_an_llm_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'memory.json'
            llm = LLM(path)
            llm.history = [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': str(i)} for i in range(40)]
            llm.history[0]['content'] = 'My project is Sakura and my GPU is RTX 3080.'
            generate = Mock(return_value='User works on Sakura and has an RTX 3080.')
            with patch.object(llm, '_request', generate):
                llm._refresh_summary()
            generate.assert_not_called()
            self.assertEqual(llm.summary, '')
            from response_evidence import Evidence
            llm.remember_evidence(Evidence('Noted: My GPU is RTX 3080.', 'User-provided', 1,
                                           [{'title': 'Your statement', 'kind': 'user'}], 'explicit user statement'))
            llm._refresh_summary()
            llm._save_memory()
            self.assertEqual(llm.summary, json.dumps(llm.trusted_memory[-30:], ensure_ascii=False)[:6000])
            self.assertNotIn('User works on Sakura', llm.summary)
            restored = LLM(path)
            self.assertEqual(restored.history[0]['content'], 'My project is Sakura and my GPU is RTX 3080.')
            self.assertNotIn('User works on Sakura', path.read_text())

    def test_persistence_disabled_keeps_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'memory.json'
            llm = LLM(path, persist_memory=False)
            with patch.object(llm, '_request', return_value='Short answer only.'):
                llm.chat(QUESTION)
                llm.chat('My name is Gaurav.')
            self.assertEqual(len(llm.history), 4)
            self.assertEqual(len(llm.trusted_memory), 1)
            self.assertFalse(path.exists())
            llm._save_memory()
            self.assertFalse(path.exists())
            self.assertEqual(LLM(path).history, [])

    def test_failure_does_not_save_fake_conversation(self):
        with tempfile.TemporaryDirectory() as folder:
            llm = LLM(Path(folder) / 'memory.json')
            failure = Mock(side_effect=requests.ConnectionError())
            with patch.object(llm, '_request', failure):
                llm.chat(QUESTION)
            failure.assert_called_once()
            self.assertEqual(llm.history, [])
            self.assertFalse(llm.memory_path.exists())

    def test_refusals_are_not_recorded_as_conversation(self):
        from response_evidence import UNKNOWN
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'memory.json'
            llm = LLM(path)
            llm.response_restriction_level = 'strict'
            with patch('response_evidence.retrieve', return_value=None), patch.object(llm, '_request') as generate:
                self.assertEqual(llm.chat('Is the RTX 6090 64 GB?'), UNKNOWN)
            generate.assert_not_called()
            self.assertEqual(llm.history, [])
            self.assertFalse(path.exists())


class MemoryWriteEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_stated_fact_gets_a_quiet_acknowledgement_not_a_receipt(self):
        import app as server
        from response_evidence import Evidence
        statement = Evidence('Noted: My name is Alex.', 'User-provided', 1,
                             [{'title': 'Your statement', 'kind': 'user'}], 'explicit user statement')
        model = Mock()
        model.remember_evidence.return_value = True
        with patch.object(server, 'llm', model), patch.object(server, 'tts', None), \
                patch.object(server, 'get_settings', return_value={'response_restriction_level': 'medium'}), \
                patch('response_evidence.retrieve', return_value=statement):
            result = await server.chat({'text': 'My name is Alex.', 'defer_audio': True})
        self.assertEqual(result['response_kind'], 'conversation')
        self.assertEqual(result['verification']['classification'], 'Inference')
        self.assertNotIn('verified', result['reply'])
        model.remember_exchange.assert_called_once_with('My name is Alex.', result['reply'])

    async def test_the_acknowledged_statement_survives_restart(self):
        import app as server
        from response_evidence import Evidence
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'memory.json'
            model = LLM(path)
            model.response_restriction_level = 'medium'
            statement = Evidence('Noted: My city is Pune.', 'User-provided', 1,
                                 [{'title': 'Your statement', 'kind': 'user'}], 'explicit user statement')
            with patch.object(server, 'llm', model), patch.object(server, 'tts', None), \
                    patch.object(server, 'get_settings', return_value={'response_restriction_level': 'medium'}), \
                    patch('response_evidence.retrieve', return_value=statement):
                await server.chat({'text': 'My city is Pune.', 'defer_audio': True})
            restored = LLM(path)
            self.assertEqual(len(restored.trusted_memory), 1)
            self.assertEqual(restored.trusted_memory[0]['classification'], 'User-provided')
            self.assertEqual([item['role'] for item in restored.history], ['user', 'assistant'])
            self.assertEqual(restored.history[0]['content'], 'My city is Pune.')

    async def test_strict_mode_saves_the_statement_but_still_refuses_to_assert_it(self):
        import app as server
        from response_evidence import Evidence, UNKNOWN
        statement = Evidence('Noted: My name is Alex.', 'User-provided', 1,
                             [{'title': 'Your statement', 'kind': 'user'}], 'explicit user statement')
        model = Mock()
        model.remember_evidence.return_value = True
        with patch.object(server, 'llm', model), patch.object(server, 'tts', None), \
                patch.object(server, 'get_settings', return_value={'response_restriction_level': 'strict'}), \
                patch('response_evidence.retrieve', return_value=statement):
            result = await server.chat({'text': 'My name is Alex.', 'defer_audio': True})
        self.assertEqual(result['reply'], UNKNOWN)
        model.remember_evidence.assert_called_once()
        model.remember_exchange.assert_not_called()


if __name__ == '__main__':
    unittest.main()
