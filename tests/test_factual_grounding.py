import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import factual_grounding as facts
from llm import LLM
from tts import polish_spoken_text


class FactualGroundingTests(unittest.TestCase):
    def test_family_table_reads_exact_5060_column_and_ti_options(self):
        page='<table><tr><th></th><th></th><th>GeForce RTX 5060 Ti</th><th>GeForce RTX 5060</th></tr><tr><td>Memory Specs:</td><td>Standard Memory Config</td><td>16 GB / 8 GB GDDR7</td><td>8 GB GDDR7</td></tr></table>'
        self.assertEqual(facts._model_memory(page,'5060'),(8,))
        self.assertEqual(facts._model_memory(page,'5060','TI'),(8,16))
        self.assertIsNone(facts._model_memory(page,'5080'))
        response=Mock(content=page.encode(),text=page)
        with patch.object(facts.requests,'get',return_value=response):
            self.assertIn('RTX 5060 with 8 GB',facts.gpu_memory_lookup('RTX 5060 VRAM?'))
            self.assertIn('8 GB or 16 GB',facts.gpu_memory_lookup('RTX 5060 Ti VRAM?'))
            self.assertIn('RTX 5060 with 8 GB',facts.gpu_memory_lookup('Does RTX 5060 have 24 GB?'))

    def setUp(self):
        facts._cache.clear()

    def test_only_labelled_unambiguous_memory_is_used(self):
        self.assertEqual(facts._memory_gb('<td>Standard Memory Config</td><td>32 GB GDDR7</td>'), 32)
        self.assertIsNone(facts._memory_gb('<script>Standard Memory Config 64 GB GDDR7</script>32 GB'))
        self.assertIsNone(facts._memory_gb('Standard Memory Config 32 GB GDDR7 Standard Memory Config 64 GB GDDR7'))

    def test_reported_false_premise_is_corrected_without_generation(self):
        response = Mock(content=b'spec', text='<p>Standard Memory Config</p><p>32 GB GDDR7</p>')
        with patch.object(facts.requests, 'get', return_value=response) as get:
            answer = facts.gpu_memory_lookup('Does RTX 5090 have 64GB of VRAM?')
            self.assertIn('32 GB', answer)
            self.assertNotIn('64 GB', answer)
            self.assertIn('https://www.nvidia.com/', answer)
            self.assertNotIn('https:', polish_spoken_text(answer))
            self.assertIn('32 GB', facts.gpu_memory_lookup('RTX 5090 memory?'))
            self.assertIn('32 GB', facts.gpu_memory_lookup('RTX 5090 has 64GB?'))
            self.assertEqual(get.call_count, 1)

    def test_failure_unknown_and_unrelated_requests_do_not_fabricate_specs(self):
        with patch.object(facts.requests, 'get', side_effect=facts.requests.Timeout):
            self.assertIn('could not verify', facts.gpu_memory_lookup('RTX5090 VRAM?'))
        with patch.object(facts.requests, 'get') as get:
            self.assertIn('do not have a verified', facts.gpu_memory_lookup('RTX 6090 memory?'))
            for question in ['hello', 'do you like my pc RTX 3080 with 12GB memory?', 'Imagine a modified RTX 5090 with 64 GB', 'What is RAM?']:
                self.assertIsNone(facts.gpu_memory_lookup(question))
            get.assert_not_called()

    def test_unsupported_search_claim_never_reaches_generation(self):
        from response_evidence import UNKNOWN
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json',persist_memory=False)
            model.response_restriction_level='strict'
            with patch('response_evidence.retrieve',return_value=None),patch.object(model,'_request') as generate:
                self.assertEqual(model.chat('do u like my PC specs'),UNKNOWN)
            generate.assert_not_called()
            self.assertEqual(model.history,[])
        self.assertTrue(facts.unsupported_tool_claim('64 GB. Source: https://made-up.test/spec','How much memory?'))


class FactualEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_verified_facts_bypass_generation_for_all_pc_ai_modes(self):
        import app as server
        answer = 'NVIDIA lists the standard desktop GeForce RTX 5090 with 32 GB of VRAM.\nSource: https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/'
        for provider in ('ollama', 'gemini', 'openai'):
            for ai_vtuber in (False, True):
                model = Mock()
                with patch.object(server, 'llm', model), patch.object(server, 'get_settings', return_value={'llm_provider': provider}), patch('assistant_commands.run_command', return_value=None), patch.object(facts, 'gpu_memory_lookup', return_value=answer), patch.object(server.app.state, 'tracking_only', False, create=True):
                    result = await server.chat({'text': 'RTX5090 has 64GB VRAM?', 'defer_audio': True, 'ai_vtuber': ai_vtuber})
                self.assertEqual(result['reply'], answer)
                self.assertNotIn('Source:', result['speech_reply'])
                model.chat.assert_not_called()
                model.remember_evidence.assert_called_once()


if __name__ == '__main__':
    unittest.main()
