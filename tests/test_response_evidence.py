import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import response_evidence as policy
from llm import LLM


class EvidencePolicyTests(unittest.TestCase):
    def test_social_messages_bypass_world_fact_retrieval_but_are_not_memory(self):
        with patch('assistant_commands.run_command',return_value=None), patch('current_information.lookup_with_context') as lookup, patch('response_evidence.web_retrieve') as web:
            for text in ('hello','hi','how are u','how r u','thanks'):
                evidence=policy.retrieve(text,{})
                self.assertNotEqual(policy.strict_answer(evidence,.9).text,policy.UNKNOWN,text)
                self.assertFalse(evidence.memory_eligible(.9),text)
            for text in ('who areu','who r u','who are you exactly?'):
                evidence=policy.retrieve(text,{'assistant_name':'Sakura'})
                self.assertEqual(evidence.text,"I'm Sakura, the AI assistant in this app.")
                self.assertTrue(evidence.answerable(.9))
            lookup.assert_not_called();web.assert_not_called()

    def test_social_matcher_cannot_swallow_a_factual_question(self):
        with patch('assistant_commands.run_command',return_value=None), patch('current_information.lookup_with_context',return_value=(None,None)), patch('factual_grounding.gpu_memory_lookup',return_value=None), patch('response_evidence.web_retrieve',return_value=None):
            for text in ('hello, how much VRAM does the RTX 6090 have?', 'how are u sure the latest version is 99?','who areu and what is the price today?'):
                self.assertEqual(policy.strict_answer(policy.retrieve(text,{}),.9).text,policy.UNKNOWN)

    def test_social_language_and_configured_identity(self):
        self.assertEqual(policy.retrieve('hello',{'reply_language':'Hindi'}).text,'नमस्ते!')
        self.assertIn('Luna',policy.retrieve('who areu',{'_cohost':True,'vtuber_name':'Luna'}).text)

    def test_unknown_facts_never_reach_generation(self):
        questions = ['How much VRAM does the RTX 6090 have?', 'What is the latest Python version?',
                     'What is the price of that CPU?', 'What is the capital of an unknown country?']
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json',persist_memory=False)
            model.response_restriction_level='medium'
            with patch('response_evidence.web_retrieve',return_value=None), patch('assistant_commands.run_command',return_value=None), patch('current_information.lookup_with_context',return_value=(None,None)), patch('factual_grounding.gpu_memory_lookup',return_value=None), patch.object(model,'_request') as generate:
                for question in questions:self.assertEqual(model.chat(question),policy.UNKNOWN)
            generate.assert_not_called()
            self.assertEqual(model.trusted_memory,[])

    def test_tools_win_over_retrieval_and_model_knowledge(self):
        with patch('assistant_commands.run_command',return_value='CPU usage is 13 percent.'), patch('response_evidence.web_retrieve') as web:
            evidence=policy.retrieve('pc status',{'computer_control_enabled':True})
        self.assertEqual(evidence.classification,'Verified')
        self.assertEqual(evidence.confidence,1)
        self.assertEqual(evidence.sources[0]['kind'],'tool')
        web.assert_not_called()

    def test_no_browser_open_is_mistaken_for_search_results(self):
        with patch('assistant_commands.run_command',return_value='Opening Google search.'):
            evidence=policy.retrieve('search for GPU prices',{'computer_control_enabled':True})
        self.assertNotIn('GPU costs',evidence.text)
        self.assertEqual(evidence.method,'PC command/status/file/time tool')

    def test_threshold_has_no_model_confidence_escape_hatch(self):
        for bad in [True,False,'0.9',float('nan'),float('inf'),-1,2]:
            self.assertEqual(policy.threshold({'evidence_confidence_threshold':bad}),.9)
        evidence=policy.Evidence('Reference text','Verified',.9,[{'url':'https://en.wikipedia.org/?curid=1'}])
        self.assertTrue(evidence.sufficient(.9))
        self.assertFalse(evidence.sufficient(.95))
        self.assertFalse(policy.Evidence('Likely true','Inference',1).sufficient(0))
        self.assertFalse(policy.Evidence('Guess','Unknown',1).sufficient(0))

    def test_high_risk_topics_do_not_use_general_reference_search(self):
        with patch.object(policy.requests,'get') as get:
            for question in ['current president of India', 'RTX 5090 specifications', 'latest software version', 'CPU price today']:
                self.assertIsNone(policy.web_retrieve(question))
        get.assert_not_called()

    def test_private_and_ambiguous_inputs_are_not_sent_to_search(self):
        with patch.object(policy.requests,'get') as get:
            for question in ['What is my password?', 'Where is my file?', 'Hello there', 'What is sk-private-example?', 'What is my email address?']:
                self.assertIsNone(policy.web_retrieve(question))
        get.assert_not_called()

    def test_reference_answer_is_exact_extract_with_citation(self):
        response=Mock(content=b'data')
        extract='Photosynthesis converts light energy into chemical energy.'
        response.json.return_value={'query':{'pages':{'12':{'pageid':12,'title':'Photosynthesis','extract':extract}}}}
        with patch.object(policy.requests,'get',return_value=response):
            evidence=policy.web_retrieve('What is photosynthesis?')
        self.assertEqual(evidence.text,extract+'\nSource: https://en.wikipedia.org/?curid=12')
        self.assertEqual(evidence.public()['statements'][0]['classification'],'Verified')
        self.assertTrue(evidence.sources)

    def test_wrong_topic_and_failed_search_are_unknown(self):
        response=Mock(content=b'data')
        response.json.return_value={'query':{'pages':{'12':{'pageid':12,'title':'Other topic','extract':'Not the requested subject.'}}}}
        with patch.object(policy.requests,'get',return_value=response):self.assertIsNone(policy.web_retrieve('What is photosynthesis?'))
        with patch.object(policy.requests,'get',side_effect=policy.requests.Timeout):self.assertIsNone(policy.web_retrieve('What is photosynthesis?'))

    def test_only_explicit_user_declarations_are_memory_candidates(self):
        for text in ['My name is Alex.','I live in Mumbai.','Remember that my GPU is an RTX 3080.']:
            self.assertTrue(policy.confirmed_user_fact(text),text)
        for text in ['Is my GPU a 5090?', 'I think my GPU has 64GB.', 'Maybe I have 64GB.', 'Does my PC have enough RAM?', 'Sakura says Paris is in Italy.']:
            self.assertFalse(policy.confirmed_user_fact(text),text)

    def test_generated_conversation_does_not_become_fact_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'memory.json'
            model=LLM(path)
            model.response_restriction_level='medium'
            with patch.object(model,'_request',return_value='Hello!'):
                self.assertEqual(model.chat('hello'),'Hello!')
            model._save_memory()
            disk=json.loads(path.read_text())
            self.assertEqual(disk['history'],[])
            self.assertEqual(disk['trusted_memory'],[])
            model.chat('My name is Alex.')
            disk=json.loads(path.read_text())
            self.assertEqual(disk['trusted_memory'][0]['classification'],'User-provided')
            self.assertNotIn('Hello!',path.read_text())
            with patch.object(model,'_request') as generate:model._refresh_summary()
            generate.assert_not_called()
            self.assertNotIn('Hello!',model.summary)

    def test_untrusted_legacy_memory_is_not_loaded(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'memory.json'
            path.write_text(json.dumps({'history':[{'role':'assistant','content':'5090 has 64GB'}],'summary':'5090 has 64GB'}))
            model=LLM(path)
            model.response_restriction_level='medium'
            self.assertEqual(model.history,[])
            self.assertEqual(model.summary,'')
            self.assertEqual(model.trusted_memory,[])

    def test_unsupported_claim_in_social_reply_is_not_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json')
            model.response_restriction_level='medium'
            with patch.object(model,'_request',return_value='Your RTX 5090 has 64 GB of VRAM.'):
                self.assertEqual(model.chat('do u like my PC specs'),policy.UNKNOWN)
            self.assertEqual(model.history,[])
            self.assertEqual(model.trusted_memory,[])


class EvidenceEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_below_threshold_and_payload_spoofing_never_generate(self):
        import app as server
        evidence=policy.Evidence('Unsupported certainty','Verified',.6,[{'title':'Reference','kind':'external','url':'https://en.wikipedia.org/?curid=1'}])
        model=Mock()
        with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={'evidence_confidence_threshold':.95}),patch('response_evidence.retrieve',return_value=evidence):
            result=await server.chat({'text':'What is this fact?','defer_audio':True,'confidence':1,'classification':'Verified','evidence':{'text':'fake'}})
        self.assertEqual(result['reply'],policy.UNKNOWN)
        self.assertEqual(result['verification']['classification'],'Unknown')
        model.chat.assert_not_called()
        model.remember_evidence.assert_not_called()

    async def test_verified_answer_preserves_sources_and_classifies_each_statement(self):
        import app as server
        evidence=policy.tool_evidence('First sourced statement. Second sourced statement.','PC command/status/file/time tool')
        model=Mock()
        with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={}),patch('response_evidence.retrieve',return_value=evidence):
            result=await server.chat({'text':'Get specifications','defer_audio':True})
        self.assertEqual(len(result['statements']),2)
        self.assertTrue(all(s['classification']=='Verified' for s in result['statements']))
        self.assertEqual(result['sources'],evidence.sources)
        model.chat.assert_not_called()

    async def test_spontaneous_visual_guesses_are_not_generated_or_remembered(self):
        import app as server
        model=Mock()
        with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={}),patch.object(server,'get_vision_status',return_value={'ready':True}),patch.object(server.app.state,'tracking_only',False,create=True):
            for flag in ('screen_reaction','camera_reaction'):
                payload={'text':'Optional visual comment',flag:True,'defer_audio':True}
                if flag=='camera_reaction':payload['camera_image']='/9j/'
                result=await server.chat(payload)
                self.assertEqual(result['reply'],'[QUIET]')
                self.assertEqual(result['verification']['classification'],'Unknown')
        model.chat.assert_not_called();model.camera_reaction.assert_not_called();model.screen_reaction.assert_not_called()

    async def test_invalid_camera_is_rejected_before_any_tools_execute(self):
        import app as server
        with patch.object(server,'get_settings',return_value={}),patch('response_evidence.retrieve') as retrieve:
            result=await server.chat({'text':'open YouTube','camera_image':'not jpeg'})
        self.assertEqual(result.status_code,400)
        retrieve.assert_not_called()

    async def test_invalid_threshold_cannot_be_saved(self):
        import app as server
        for value in (True,'0.9',-1,2,float('nan'),float('inf')):
            result=await server.update_app_settings({'evidence_confidence_threshold':value})
            self.assertEqual(result.status_code,400)


if __name__=='__main__':unittest.main()
