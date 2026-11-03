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

    def test_unperformed_pc_change_is_never_claimed(self):
        self.assertTrue(facts.unsupported_action_claim('Volume has been updated to 50%.'))
        self.assertTrue(facts.unsupported_action_claim('I have set the volume to 50%.'))
        self.assertTrue(facts.unsupported_action_claim('Brightness is now at 40 percent.'))
        self.assertFalse(facts.unsupported_action_claim('System volume is 22 percent and muted.'))
        self.assertFalse(facts.unsupported_action_claim('Volume will be set to 50% now.'))
        self.assertFalse(facts.unsupported_action_claim('Volume has been updated.',
                                                        'write a pretend story'))
        self.assertTrue(facts.unsupported_tool_claim('Volume has been updated to 50%.','make it 50'))

    def test_denying_a_setting_sakura_controls_is_corrected(self):
        denied=facts.unwarranted_capability_denial("I can't increase your volume directly - that's handled by "
                                                   'the system settings.','Increase the volume to 50 percent.')
        self.assertIn('I can change your system volume from here',denied)
        self.assertIn('set brightness',facts.unwarranted_capability_denial(
            'Sorry, I cannot change your brightness; use Windows display settings.','lower the brightness to 20'))
        self.assertIn('system volume',facts.unwarranted_capability_denial(
            "I can't adjust your volume directly - that's outside what I'm able to do here.",
            'kindly bump the volume to 50'))
        # Honest refusals and unrelated answers must survive untouched.
        for reply,question in [('System volume is 18 percent.','what is my volume'),
                               ('I cannot do that because your monitor refused the DDC/CI write.','set brightness to 200 percent'),
                               ('I cannot read that file; it does not exist.','open the volume file'),
                               ("I can't help with that.",'tell me about movies'),
                               ('I am not able to find that song in the queue.','play the volume song')]:
            self.assertIsNone(facts.unwarranted_capability_denial(reply,question),(reply,question))

    def test_generated_current_setting_level_is_not_believed(self):
        # The live transcript: nothing was read, yet the reply stated "from 18% to 22%".
        self.assertTrue(facts.invented_setting_state('Volume is going from 18% to 22%.','22'))
        self.assertTrue(facts.invented_setting_state('Your brightness is now at 30 percent.','make it dimmer'))
        for reply,question in [('Your speaker volume is limited to 100 percent.','why is my volume capped'),
                               ('If the volume is at 50 percent it will be loud.','is 50 loud'),
                               ('System volume is 18 percent.','the volume is 18 percent please confirm'),
                               ("I can't tell without reading it.",'what is my volume')]:
            self.assertFalse(facts.invented_setting_state(reply,question),(reply,question))

    def test_completion_wording_variants_and_non_claims(self):
        for text in ['I set the volume to 50%.','Done, volume set to 50%.',
                     'I changed your brightness to 40%.',"I've turned it down.",
                     'Volume successfully adjusted to 50%.','Volume is now at 50%.',
                     'Brightness is now at 40%.']:
            self.assertTrue(facts.unsupported_action_claim(text),text)
        for text in ['Set the volume to 50%.','Volume will be set to 50% now.',
                     'I have not changed your brightness.',"I didn't set the volume.",
                     'If I set the volume to 50%, you will hear it.',
                     'Was the volume set to 50%?', 'System volume is 22 percent and muted.',
                     'Keep the volume set to 50%.', 'Leave your brightness set to 40%.']:
            self.assertFalse(facts.unsupported_action_claim(text),text)

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
