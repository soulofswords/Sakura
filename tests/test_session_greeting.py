import json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from llm import LLM
import app as server

class SessionChatTests(unittest.TestCase):
 def test_default_app_session_does_not_load_or_save_chat(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'conversation-memory.json';settings=Path(folder)/'settings.json';settings.write_text('{"voice":"saved"}')
   path.write_text(json.dumps({'history':[{'role':'assistant','content':'Old invented history'}],'summary':'Old summary'}))
   path.with_suffix('.tmp').write_text('old partial write')
   backup=path.with_name(path.name+'.before-grounding-2026-10-21.bak');backup.write_text('old archived conversation')
   model=LLM(path,persist_memory=False)
   self.assertEqual(model.history,[]);self.assertEqual(model.summary,'');self.assertFalse(path.exists());self.assertFalse(backup.exists());self.assertFalse(path.with_suffix('.tmp').exists())
   model.remember_exchange('my name is A','Hello A')
   with patch.object(model,'_request',return_value='You said A.'):
    self.assertEqual(model.chat('What is my name?'),'You told me: my name is A')
   self.assertEqual(model.refresh_memory(),2,'Status must not erase current session')
   self.assertFalse(path.exists(),'No session chat is written to disk')
   reopened=LLM(path,persist_memory=False);self.assertEqual(reopened.history,[]);self.assertEqual(reopened.summary,'')
   self.assertEqual(settings.read_text(),'{"voice":"saved"}')
 def test_clear_removes_trusted_ledger_without_model_summarization(self):
  from response_evidence import Evidence
  with tempfile.TemporaryDirectory() as folder:
   model=LLM(Path(folder)/'memory.json',persist_memory=False)
   model.remember_evidence(Evidence('My name is A','User-provided',1.0))
   with patch.object(model,'_request') as generate:
    model._refresh_summary();model.clear_history();model._refresh_summary()
   generate.assert_not_called()
   self.assertEqual(model.history,[]);self.assertEqual(model.trusted_memory,[]);self.assertEqual(model.summary,'')
   self.assertFalse(model.memory_path.exists())

class GreetingWaveTests(unittest.IsolatedAsyncioTestCase):
 async def test_local_and_cloud_greeting_requests_wave_only_with_rig_capability(self):
  for provider in ['local','gemini','openai']:
   for capable in [True,False]:
    model=Mock();model.chat.return_value='Hello!'
    with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={'llm_provider':provider}),patch('assistant_commands.run_command',return_value=None),patch('current_information.lookup_with_context',return_value=(None,None)),patch.object(server.app.state,'tracking_only',False,create=True):
     result=await server.chat({'text':'hello','defer_audio':True,'avatar_can_greet':capable})
    self.assertEqual(result['reply'],'Hello!');self.assertEqual(result['avatar_motion'],'greeting_wave' if capable else None)
 async def test_combined_greeting_waves_and_answers_without_generation(self):
  for text in ('hello how are u','Hello, how are you?','hello! how r u'):
   model=Mock()
   with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={}),patch('assistant_commands.run_command',return_value=None),patch.object(server.app.state,'tracking_only',False,create=True):
    result=await server.chat({'text':text,'defer_audio':True,'avatar_can_greet':True})
   self.assertEqual(result['avatar_motion'],'greeting_wave')
   self.assertIn('How are you?',result['speech_reply'])
   model.chat.assert_not_called()
 async def test_no_wave_for_non_greetings_or_tracking_only(self):
  for text,tracking in (('how are u',False),('hello',True),('write hello world code',False)):
   with patch.object(server,'get_settings',return_value={}),patch('assistant_commands.run_command',return_value=None),patch('current_information.lookup_with_context',return_value=(None,None)),patch.object(server.app.state,'tracking_only',tracking,create=True):
    result=await server.chat({'text':text,'defer_audio':True,'avatar_can_greet':True})
   self.assertIsNone(result['avatar_motion'])
 async def test_other_text_does_not_wave(self):
  model=Mock();model.chat.return_value='Here is the code.'
  with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={}),patch('assistant_commands.run_command',return_value=None),patch('current_information.lookup_with_context',return_value=(None,None)):
   result=await server._chat_core({'text':'write hello world code','defer_audio':True,'avatar_can_greet':True})
  self.assertIsNone(result['avatar_motion'])

if __name__=='__main__':unittest.main()
