import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

from llm import LLM
from response_evidence import response_answer, Evidence


class NormalResponseTests(unittest.TestCase):
    def test_missing_evidence_allows_regular_generation(self):
        self.assertIsNone(response_answer(None,.9,'What is a compiler?',{'response_restriction_level':'off'}))
        self.assertIsNone(response_answer(Evidence('Missing evidence'),.9,'Tell me something',{'response_restriction_level':'off'}))

    def test_general_question_reaches_local_or_cloud_generation(self):
        for provider in ('ollama','gemini','openai'):
            with tempfile.TemporaryDirectory() as folder:
                model=LLM(Path(folder)/'memory.json');model.provider=provider
                with patch('response_evidence.retrieve',return_value=None),patch.object(model,'_request',return_value='A compiler translates source code into another form.') as generate:
                    self.assertEqual(model.chat('What is a compiler?'),'A compiler translates source code into another form.')
                generate.assert_called_once()
                self.assertEqual(model.trusted_memory,[])

    def test_invented_completed_action_is_replaced_even_with_restriction_off(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json');model.response_restriction_level='off'
            with patch('response_evidence.retrieve',return_value=None),patch.object(model,'_request',return_value='Volume has been updated to 50%.') as generate:
                reply=model.chat('confirmed')
        self.assertNotIn('has been updated',reply)
        self.assertIn('no PC action was run',reply)
        self.assertTrue(generate.called)

    def test_simple_past_success_claim_is_blocked_with_restriction_off(self):
        for draft in ['I set the volume to 50%.','Done, volume set to 50%.','I changed your brightness to 40%.']:
            with self.subTest(draft=draft):
                model=LLM(persist_memory=False);model.response_restriction_level='off'
                with patch('response_evidence.retrieve',return_value=None),patch.object(model,'_request',return_value=draft):
                    reply=model.chat('confirmed')
                self.assertIn('no PC action was run',reply)
                self.assertNotEqual(reply,draft)

    def test_denied_pc_capability_is_replaced_with_restriction_off(self):
        # The transcript the user reported: no command matched, so the model invented a
        # "go to your sound controls" excuse for a setting Sakura really controls.
        model=LLM(persist_memory=False);model.response_restriction_level='off'
        draft=("I can't increase your volume directly - that's handled by the system settings. "
               'Try going to your sound controls and adjusting it there.')
        with patch('response_evidence.retrieve',return_value=None),patch.object(model,'_request',return_value=draft):
            reply=model.chat('Increase the volume to 50 percent.')
        self.assertNotEqual(reply,draft)
        self.assertIn('I can change your system volume from here',reply)
        self.assertNotIn('sound controls',reply)

    def test_invented_current_level_is_replaced_with_restriction_off(self):
        model=LLM(persist_memory=False);model.response_restriction_level='off'
        draft='Got it! Volume is going from 18% to 22%, so we are moving up a bit - no problem.'
        with patch('response_evidence.retrieve',return_value=None),patch.object(model,'_request',return_value=draft):
            reply=model.chat('22')
        self.assertNotIn('18%',reply)
        self.assertIn('I have not read your current setting',reply)

    def test_viewer_question_is_not_rejected_by_social_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json')
            with patch('response_evidence.retrieve',return_value=None),patch.object(model,'_request',return_value='A compiler translates source code.'):
                self.assertEqual(model.viewer_reply('Viewer','What is a compiler?'),'A compiler translates source code.')


class NormalEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_chat_preserves_greeting_wave(self):
        import app as server
        model=Mock();model.chat.return_value='Hello!'
        with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={'response_restriction_level':'off'}),patch.object(server.app.state,'tracking_only',False,create=True),patch('assistant_commands.run_command',return_value=None),patch('factual_grounding.gpu_memory_lookup',return_value=None),patch('current_information.lookup_with_context',return_value=(None,None)):
            result=await server.chat({'text':'hello how are u','defer_audio':True,'avatar_can_greet':True})
        self.assertEqual(result['avatar_motion'],'greeting_wave')
        self.assertEqual(result['response_policy'],'Normal')
        self.assertEqual(result['response_kind'],'conversation')
        model.chat.assert_called_once()

    async def test_viewer_endpoint_returns_normal_speech(self):
        import app as server
        model=Mock();model.viewer_reply.return_value='Glad to hear that!'
        with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={'response_restriction_level':'off'}):
            result=await server.reply_vtuber({'author':'Viewer','text':'I am also great'})
        self.assertEqual(result['speech_reply'],'Glad to hear that!')
        self.assertEqual(result['response_policy'],'Normal')
