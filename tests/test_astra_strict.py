import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from llm import LLM
from response_evidence import Evidence, UNKNOWN, strict_answer, tool_evidence, LOCAL_SOURCES


class AstraStrictTests(unittest.TestCase):
    def test_inference_unknown_and_user_only_evidence_cannot_answer(self):
        for label in ('Inference','Unknown','User-provided'):
            for minimum in (0,.9,1):
                self.assertEqual(strict_answer(Evidence('A plausible claim',label,1),minimum).text,UNKNOWN)
        self.assertEqual(strict_answer(None,0).text,"I couldn't verify that.")

    def test_verified_label_without_approved_citation_is_rejected(self):
        records=[Evidence('A fact','Verified',1),
                 Evidence('A fact','Verified',1,[{'kind':'external','url':'https://made-up.test/'}],'reference retrieval'),
                 Evidence('A fact','Verified',1,[{'kind':'tool','url':'sakura://made-up'}],'PC command/status/file/time tool')]
        for record in records:self.assertEqual(strict_answer(record,.9).text,UNKNOWN)
        for url in ('https://en.wikipedia.org.evil/?curid=1','https://en.wikipedia.org:123/?curid=1','https://[invalid'):
            record=Evidence('Source: '+url,'Verified',1,[{'kind':'external','url':url}],'reference retrieval')
            self.assertEqual(strict_answer(record,.9).text,UNKNOWN)

    def test_registered_tool_and_manufacturer_sources_pass(self):
        evidence=tool_evidence('CPU usage is 13 percent.','PC command/status/file/time tool')
        self.assertEqual(strict_answer(evidence,.9).text,evidence.text)
        self.assertTrue(evidence.public()['statements'][0]['sources'])
        url='https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/'
        evidence=Evidence('32 GB.\nSource: '+url,'Verified',1,[{'kind':'external','url':url}],'manufacturer specification lookup')
        self.assertTrue(evidence.answerable(.9))

    def test_failed_lookup_and_all_generation_requests_never_call_model(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json',persist_memory=False)
            model.response_restriction_level='strict'
            with patch('response_evidence.retrieve',return_value=None),patch.object(model,'_request') as generate:
                for question in ('hello','How are you?','Write a fictional story','Is the RTX 6090 64 GB?'):
                    self.assertEqual(model.chat(question),UNKNOWN)
            generate.assert_not_called()
            self.assertEqual(model.trusted_memory,[])

    def test_memory_rules_differ_from_answer_rules(self):
        source=[{'kind':'user','title':'Your statement'}]
        user=Evidence('My name is Alex.','User-provided',1,source,'explicit user statement')
        self.assertTrue(user.memory_eligible(.9))
        self.assertFalse(user.answerable(.9))
        self.assertFalse(Evidence('Guess','Inference',1).memory_eligible(0))
        self.assertFalse(Evidence('Guess','Verified',1).memory_eligible(0))
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json')
            self.assertFalse(model.remember_evidence(Evidence('Guess','Inference',1)))
            self.assertTrue(model.remember_evidence(user))
            self.assertEqual(len(model.trusted_memory),1)
            self.assertEqual(model.trusted_memory[0]['classification'],'User-provided')

    def test_user_claim_is_only_quoted_as_a_record_not_promoted_to_world_fact(self):
        from response_evidence import retrieve
        records=[{'classification':'User-provided','text':'Noted: My GPU is a 64 GB RTX 5090.'}]
        with patch('assistant_commands.run_command',return_value=None),patch('factual_grounding.gpu_memory_lookup',return_value=None),patch('current_information.lookup_with_context',return_value=(None,None)):
            result=retrieve('What is my GPU?',{},records)
        self.assertTrue(result.answerable(.9))
        self.assertEqual(result.text,'You told me: My GPU is a 64 GB RTX 5090.')
        self.assertEqual(result.sources[0]['url'],LOCAL_SOURCES['confirmed user memory'])


class AstraStrictEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_public_request_can_enable_parametric_fallback(self):
        import app as server
        model=Mock()
        for raw in (None,Evidence('Guess','Inference',1),Evidence('User claim','User-provided',1),Evidence('Uncited','Verified',1)):
            with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={'response_restriction_level':'strict'}),patch('response_evidence.retrieve',return_value=raw):
                result=await server.chat({'text':'Answer anything','defer_audio':True,'strict':False,'classification':'Verified','confidence':1})
            self.assertEqual(result['reply'],UNKNOWN)
            self.assertEqual(result['response_policy'],'Astra Strict Mode')
            self.assertEqual(result['verification']['classification'],'Unknown')
        model.chat.assert_not_called();model._request.assert_not_called();model.remember_evidence.assert_not_called()

    async def test_internal_retrieval_failure_returns_exact_refusal(self):
        import app as server
        with patch.object(server,'get_settings',return_value={}),patch('response_evidence.retrieve',side_effect=RuntimeError('failed')):
            result=await server.chat({'text':'Get a fact','defer_audio':True})
        self.assertEqual(result['reply'],UNKNOWN)
        self.assertEqual(result['speech_reply'],UNKNOWN)

    async def test_medium_chat_reviews_a_desktop_action_instead_of_running_it(self):
        import app as server
        settings={'response_restriction_level':'medium','computer_control_enabled':True}
        with patch.object(server,'get_settings',return_value=dict(settings)), \
                patch('desktop_control.execute_action') as execute, \
                patch('assistant_commands.run_command') as command:
            result=await server.chat({'text':'click save'})
        self.assertTrue(result.get('command_approval'))
        self.assertIn('Review this PC action before it runs',result['reply'])
        execute.assert_not_called();command.assert_not_called()

    async def test_medium_chat_reads_an_attachment_instead_of_dropping_it(self):
        import app as server
        seen=[]
        async def core(payload,resolved_reply=None,skip_retrieval=False,preflight=False,offer_search=False):
            seen.append(preflight)
            return None if preflight else {'reply':'Three names are listed.','audio':None}
        with patch.object(server,'get_settings',return_value={'response_restriction_level':'medium'}), \
                patch.object(server,'_chat_core',core):
            result=await server.chat({'text':'summarize this file','attachments':['tok_abc']})
        self.assertEqual(seen,[True,False]);self.assertEqual(result['reply'],'Three names are listed.')
        self.assertEqual(result['response_policy'],'Medium')


if __name__=='__main__':unittest.main()
