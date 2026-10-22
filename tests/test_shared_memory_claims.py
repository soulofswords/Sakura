from tests.generation_quality_isolation import GenerationQualityIsolation
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from llm import LLM
from persona_grounding import unsupported_shared_history
BAD="You're probably referring to that Lineos game or app we've been discussing lately."

class SharedMemoryClaims(GenerationQualityIsolation,unittest.TestCase):
 def test_new_unfamiliar_word_is_not_prior_context(self):
  prior=[{'role':'user','content':'Mumbai news'},{'role':'assistant','content':'We discussed Lineos.'}]
  self.assertTrue(unsupported_shared_history(BAD,'The Lineos',prior))
  self.assertFalse(unsupported_shared_history("I don't know what Lineos refers to. Could you clarify?",'The Lineos',prior))
  self.assertFalse(unsupported_shared_history("We haven't discussed Lineos.",'The Lineos',prior))
  prior.append({'role':'user','content':'Tell me about Lineos, the game.'})
  self.assertFalse(unsupported_shared_history(BAD,'The Lineos',prior))
 def test_generation_retries_without_saving_false_shared_memory(self):
  with tempfile.TemporaryDirectory() as folder:
   model=LLM(Path(folder)/'memory.json',persist_memory=False)
   with patch.object(model,'_request',side_effect=[BAD,'Could you repeat that?']) as request:
    self.assertEqual(model.chat('The Lineos'),'Could you repeat that?');self.assertEqual(request.call_count,2)
   self.assertNotIn(BAD,[m['content'] for m in model.history])
   with patch.object(model,'_request',return_value=BAD):
    self.assertIn('say that another way',model.chat('The Lineos'))
 def test_fiction_and_genuine_memory_remain_allowed(self):
  self.assertFalse(unsupported_shared_history('We discussed the weather in Delhi.','What did we discuss?',[{'role':'user','content':'Weather in Delhi'}]))
  self.assertFalse(unsupported_shared_history(BAD,'Write a story about a fictional app.',[]))

if __name__=='__main__':unittest.main()
