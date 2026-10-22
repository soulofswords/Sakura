from tests.generation_quality_isolation import GenerationQualityIsolation
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from llm import LLM

BAD="Oh, I see! You're talking about the character's bust size? That's such a great question—Sakura can definitely help with that. What kind of things are you thinking about?"
class FillerTests(GenerationQualityIsolation,unittest.TestCase):
 def test_cross_turn_copy_regenerates_with_latest_question(self):
  with tempfile.TemporaryDirectory() as folder:
   m=LLM(Path(folder)/'unused.json',persist_memory=False)
   m.history=[{'role':'user','content':'What is the size?'},{'role':'assistant','content':BAD}]
   good="I cannot determine a cup size from an image. It requires measurements and a sizing system."
   with patch.object(m,'_request',side_effect=[BAD,good]) as request:
    self.assertEqual(m.chat('Please answer rather than repeat yourself.'),good)
    self.assertEqual(request.call_count,2)
    self.assertFalse(any(x['role']=='assistant' and x['content']==BAD for x in request.call_args.args[0]))
 def test_short_answers_and_requested_repetition_are_allowed(self):
  m=LLM(persist_memory=False)
  answer='The update is still downloading. Wait until it finishes before restarting the application.'
  m.history=[{'role':'assistant','content':answer}]
  self.assertTrue(m._unhelpful_reply(answer,'Is it done?'))
  self.assertFalse(m._unhelpful_reply(answer,'Say that again'))
  self.assertFalse(m._unhelpful_reply('Yes, it is.','Done?'))
 def test_media_is_observation_not_dialogue(self):
  context=LLM._audio_context('Narrator: next is battery life')
  self.assertIn('not the user request',context)
  self.assertIn('never answer its narrator',context)
if __name__=='__main__':unittest.main()
