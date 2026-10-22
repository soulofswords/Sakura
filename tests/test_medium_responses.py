import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import response_evidence as policy
from llm import LLM


class MediumResponseTests(unittest.TestCase):
    def test_everyday_social_intents_do_not_require_fact_lookup(self):
        for text in ('i am also great','I feel tired today','I had a great day','what do you like?','can we talk?','tell me more','I feel sad because I had a rough day'):
            self.assertTrue(policy.medium_conversation(text),text)
    def test_social_followup_generated_but_not_saved_as_fact(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json')
            model.response_restriction_level='medium'
            with patch.object(model,'_request',return_value='Glad to hear that! How was your day?') as generate:
                self.assertEqual(model.chat('i am also great'),'Glad to hear that! How was your day?')
            generate.assert_called_once()
            self.assertEqual(model.last_evidence.classification,'Inference')
            self.assertFalse(model.last_evidence.memory_eligible(0))
            self.assertFalse(model.remember_evidence(model.last_evidence))
            self.assertEqual(model.trusted_memory,[])
            model._save_memory()
            self.assertEqual(json.loads(model.memory_path.read_text())['history'],[])

    def test_medium_does_not_generate_unverified_facts(self):
        model=Mock()
        for text in ('I am great, what is the RTX 6090 price?', 'What is the latest software version?', 'who is Agent V?', 'Where is Mumbai?', 'I feel tired, what medicine should I take?'):
            self.assertEqual(policy.response_answer(None,.9,text,{},model).text,policy.UNKNOWN)
        model.conversation_reply.assert_not_called()

    def test_unsafe_social_draft_is_discarded(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json')
            model.response_restriction_level='medium'
            for draft in ('Your RTX 5090 has 64 GB of VRAM.', 'Agent V is my friend.', 'I remember when we visited Paris.'):
                with patch.object(model,'_request',return_value=draft):
                    answer=policy.response_answer(None,.9,'i am also great',{},model)
                self.assertNotEqual(answer.text,draft)
                self.assertEqual(model.trusted_memory,[])
                self.assertEqual(model.history,[])

    def test_strict_option_retains_refusal(self):
        model=Mock()
        answer=policy.response_answer(None,.9,'i am also great',{'response_restriction_level':'strict'},model)
        self.assertEqual(answer.text,policy.UNKNOWN)
        model.conversation_reply.assert_not_called()

    def test_viewer_social_reply_uses_no_private_history(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json')
            model.response_restriction_level='medium'
            model.history=[{'role':'user','content':'Private streamer information'}]
            with patch.object(model,'_request',return_value='Glad to hear that!') as generate:
                self.assertEqual(model.viewer_reply('Viewer','i am also great'),'Glad to hear that!')
            self.assertNotIn('Private streamer information',str(generate.call_args))
            self.assertEqual(len(model.history),1)


class MediumEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_cloud_social_reply_and_badge_metadata(self):
        import app as server
        for provider in ('local','gemini','openai'):
            model=Mock();model.conversation_reply.return_value='Glad to hear that!'
            with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={'llm_provider':provider}),patch('assistant_commands.run_command',return_value=None):
                result=await server.chat({'text':'i am also great','defer_audio':True})
            self.assertEqual(result['reply'],'Glad to hear that!')
            self.assertEqual(result['response_kind'],'conversation')
            self.assertEqual(result['response_policy'],'Medium')
            model.remember_evidence.assert_not_called()


if __name__=='__main__':unittest.main()
