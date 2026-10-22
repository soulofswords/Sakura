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
