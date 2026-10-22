from tests.generation_quality_isolation import GenerationQualityIsolation
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from llm import LLM
from persona_grounding import unsupported_persona,grounded_history,unreliable_summary,referenced_invented_lore

BAD="Agent V? That's my friend from the vending machine world. I've been in charge of its snacks since 2024."

class PersonaGrounding(GenerationQualityIsolation,unittest.TestCase):
 def test_rejects_invented_biography_preserves_honest_and_creative_answers(self):
  for text in [BAD,"I don't need to explain myself. Just ask.","My friend Alex lives in a secret world.","That's my secret weapon. It spits out chaos."]:
   self.assertTrue(unsupported_persona(text),text)
  for text in ["Hello, my friend!", "I made that up earlier. I don't have a real friend called Agent V.","Your friend could try restarting the app.","I can help write a fictional character."]:
   self.assertFalse(unsupported_persona(text),text)
  self.assertFalse(unsupported_persona(BAD,'Write a fictional story about a robot and its friend.'))
 def test_bad_reply_retried_and_not_committed(self):
  with tempfile.TemporaryDirectory() as folder:
   model=LLM(Path(folder)/'memory.json')
   good="I made that name up earlier. I don't know a real person called Agent V."
   with patch.object(model,'_request',side_effect=[BAD,good]) as request:
    self.assertEqual(model.chat('who is agent V?'),good)
    self.assertEqual(request.call_count,2)
   self.assertNotIn(BAD,[m['content'] for m in model.history])
   size=len(model.history)
   with patch.object(model,'_request',return_value=BAD):self.assertEqual(model.chat('who is he?'),'')
   self.assertEqual(len(model.history),size)
 def test_identity_has_truthful_short_fallback_not_evasive_persona(self):
  with tempfile.TemporaryDirectory() as folder:
   model=LLM(Path(folder)/'memory.json')
   for language in ['English','Hindi','Hinglish']:
    model.reply_language=language
    with patch.object(model,'_request',return_value="I don't need to explain myself."):
     reply=model.chat('who are u exactly?')
    self.assertIn('Sakura',reply);self.assertLess(len(reply.split()),25)
   model.set_vtuber_name('Luna')
   with patch.object(model,'_request',return_value=BAD):self.assertIn('Luna',model.chat('who are you?',cohost=True))
 def test_legacy_generated_memory_is_not_loaded_as_evidence(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'memory.json'
   path.write_text(json.dumps({'history':[{'role':'assistant','content':BAD}],'summary':BAD}))
   model=LLM(path)
   self.assertEqual(model.history,[]);self.assertEqual(model.summary,'');self.assertEqual(model.trusted_memory,[])
 def test_summary_cannot_synthesize_new_facts(self):
  from response_evidence import Evidence
  with tempfile.TemporaryDirectory() as folder:
   model=LLM(Path(folder)/'memory.json')
   model.remember_evidence(Evidence('My GPU is RTX 3080.','User-provided',1,[{'kind':'user'}],'explicit user statement'))
   model.history=[{'role':'assistant','content':BAD}]*40
   with patch.object(model,'_request') as request:model._refresh_summary()
   request.assert_not_called();self.assertNotIn(BAD,model.summary);self.assertIn('RTX 3080',model.summary)
 def test_followup_corrects_invented_name_without_more_speculation(self):
  with tempfile.TemporaryDirectory() as folder:
   model=LLM(Path(folder)/'memory.json');model.history=[{'role':'user','content':'hello'},{'role':'assistant','content':BAD}]
   with patch.object(model,'_request') as request:
    answer=model.chat('who is Agent V?')
    self.assertIn('made that detail up',answer);self.assertIn("shouldn't",answer);request.assert_not_called()
   self.assertFalse(referenced_invented_lore('Who is Taylor?',model.history))

 def test_wellbeing_reply_does_not_answer_pc_opinion(self):
  with tempfile.TemporaryDirectory() as folder:
   model=LLM(Path(folder)/'memory.json')
   good="Your RTX 3080 and 32 GB RAM are a capable gaming setup."
   with patch.object(model,'_request',side_effect=["I’m good.",good]) as request:
    self.assertEqual(model.chat('do u like my pc specs'),good)
    self.assertEqual(request.call_count,2)
   self.assertFalse(model._unhelpful_reply("I'm good.",'How are you?'))

 def test_explicit_story_remains_in_context(self):
  history=[{'role':'user','content':'Write a fictional story about a robot.'},{'role':'assistant','content':BAD}]
  self.assertEqual(list(grounded_history(history)),history)
  self.assertFalse(referenced_invented_lore('Who is Agent V?',history))

if __name__=='__main__':unittest.main()
