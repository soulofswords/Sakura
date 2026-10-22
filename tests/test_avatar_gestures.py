from tests.generation_quality_isolation import GenerationQualityIsolation
import unittest
from unittest.mock import Mock,patch
from avatar_gestures import conversational_gesture
from spoken_text import clean_performance_markup, performance_mood
from llm import LLM
import app as server

class GestureTests(unittest.TestCase):
 def test_sparkling_eyes_are_expression_metadata_not_dialogue(self):
  for raw in ['eyes sparkle Well, let us look at the role.', 'Hmm? eyes sparkle Well, let us look at the role.', '*eyes sparkle* Well, let us look at the role.', '(eyes sparkle) Well, let us look at the role.']:
   self.assertEqual(performance_mood(raw),'sparkle')
   self.assertNotIn('eyes sparkle',LLM._spoken_reply(raw))
  for raw in ['My eyes sparkle when I laugh.', 'Why do eyes sparkle?', 'The eyes sparkle under these lights.']:
   self.assertEqual(clean_performance_markup(raw),raw)
  model=LLM.__new__(LLM);model.reply_language='English';model.user_address='none'
  with patch.object(model,'_request_raw',return_value='Hmm? eyes sparkle Well, let us look at the role.'):
   self.assertNotIn('eyes sparkle',model._request([{'role':'user','content':'Can you help with my CV?'}]))
  self.assertEqual(model.last_reply_mood,'sparkle')
 def test_heart_context_and_explicit_request(self):
  for text in ['You are my heart.','You’re my heartbeat!','please tap your chest','Can you tap your chest?']:
   self.assertEqual(conversational_gesture(text,"You're my heartbeat too."),'chest_tap')
  for text in ['My heart hurts','You are not my heart','Explain the heart','She said you are my heart','tap the keyboard']:
   self.assertIsNone(conversational_gesture(text,'Your heartbeat matters.'))
  self.assertIsNone(conversational_gesture('You are my heart.',"I can't do that."))
 def test_eye_direction_becomes_metadata_without_spoken_narration(self):
  for prefix in ['eyes widen slightly ', '*eyes widen slightly* ', '(eyes widen slightly) ', 'eyes widen slightly. ']:
   raw=prefix+'Your PC is capable.'
   self.assertEqual(performance_mood(raw),'surprised')
   self.assertEqual(LLM._spoken_reply(raw),'Your PC is capable.')
  for raw in ['My eyes widen when I am surprised.', 'Why do eyes widen?', 'The eyes widen under these conditions.']:
   self.assertEqual(clean_performance_markup(raw),raw)
  model=LLM.__new__(LLM);model.reply_language='English';model.user_address='none'
  with patch.object(model,'_request_raw',return_value='eyes widen slightly Your PC is capable.'):
   self.assertEqual(model._request([{'role':'user','content':'Do you like my PC?'}]),'Your PC is capable.')
  self.assertEqual(model.last_reply_mood,'surprised')

 def test_chest_direction_is_not_spoken(self):
  for text in ['🫀 Taps chest gently …then I’ll never let go.','*taps her chest gently* Then I’ll never let go.','(taps chest) Then I’ll never let go.']:
   self.assertNotIn('taps',LLM._spoken_reply(text).lower())
  for text in ['My heart beats fast.','The doctor taps your chest during an exam.','Tap your chest gently to demonstrate.']:
   self.assertEqual(clean_performance_markup(text),text)

class GestureEndpointTests(GenerationQualityIsolation,unittest.IsolatedAsyncioTestCase):
 async def test_local_and_cloud_share_gesture_capability_guard(self):
  for provider in ['local','gemini','openai']:
   for capable in [False,True]:
    model=Mock();model.chat.return_value="You're my heartbeat too."
    with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={'llm_provider':provider}),patch('assistant_commands.run_command',return_value=None),patch('current_information.lookup_with_context',return_value=(None,None)),patch.object(server.app.state,'tracking_only',False,create=True):
     result=await server._chat_core({'text':'You are my heart.','defer_audio':True,'avatar_can_chest_tap':capable})
     self.assertEqual(result['avatar_motion'],'chest_tap' if capable else None)
     self.assertEqual(result['reply'],"You're my heartbeat too.")

if __name__=='__main__':unittest.main()
