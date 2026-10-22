import unittest
from unittest.mock import Mock, patch
from avatar_gestures import laugh_request
import app as server

class DirectLaugh(unittest.TestCase):
 def test_direct_requests(self):
  for text in ['laugh','Laugh!','can you laugh?','Sakura, please laugh for me','give me a laugh','giggle','hanso','हँसो']:
   self.assertEqual(laugh_request(text),'laugh',text)
  for text in ['laugh harder','belly laugh','Please laugh holding your stomach','Could you laugh with your whole body?']:
   self.assertEqual(laugh_request(text),'laugh_bend',text)
  for text in ["don't laugh",'stop laughing','why do people laugh','I said "laugh"','she said laugh','can you not laugh','laugh at him','tell me a joke','my belly hurts']:
   self.assertIsNone(laugh_request(text),text)

class DirectLaughEndpoint(unittest.IsolatedAsyncioTestCase):
 async def test_command_skips_llm_and_tts_for_local_and_cloud(self):
  for provider in ['local','gemini','openai']:
   for text,style in [('laugh','laugh'),('laugh harder','laugh_bend')]:
    model=Mock();voice=Mock()
    with patch.object(server,'llm',model),patch.object(server,'tts',voice),patch.object(server,'get_settings',return_value={'llm_provider':provider}),patch.object(server.app.state,'tracking_only',False,create=True):
     result=await server._chat_core({'text':text,'avatar_can_dance':True,'defer_audio':True,'ai_vtuber':True})
    self.assertEqual(result['avatar_motion'],style)
    self.assertTrue(result['performance_audio'].split('?')[0].endswith('laugh-belly.wav' if style=='laugh_bend' else 'laugh-short.wav'))
    model.chat.assert_not_called();voice.speak_to_file_async.assert_not_called()
 async def test_no_unsupported_animation(self):
  model=Mock()
  with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={}),patch.object(server.app.state,'tracking_only',False,create=True):
   result=await server._chat_core({'text':'laugh','avatar_can_dance':False,'defer_audio':True})
  self.assertIsNone(result['avatar_motion']);self.assertIsNone(result['performance_audio'])
  self.assertIn('PMX or VRM',result['reply']);model.chat.assert_not_called()

if __name__=='__main__':unittest.main()
