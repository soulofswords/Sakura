from tests.generation_quality_isolation import GenerationQualityIsolation
import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from llm import LLM
from hindi_conversation import common_reply,garbled_reply
from voice_catalog import voice_language
class HindiConversation(GenerationQualityIsolation,unittest.TestCase):
 def test_common_spoken_and_romanized_intents(self):
  with tempfile.TemporaryDirectory() as folder:
   model=LLM(Path(folder)/'memory.json',persist_memory=False);model.reply_language='Hindi'
   for text in ['appko hindi ati hai','aapko hindi aati hai?','आपको हिंदी आती है?','How are you?','आप कैसे हो?','app ladke ho kya ladki','aap ladke ho kya ladki','आप लड़के हो या लड़की?']:
    with patch.object(model,'_request') as request:
     reply=model.chat(text);self.assertTrue(LLM._matches_reply_language(reply,'Hindi'),text);request.assert_not_called()
     self.assertLess(len(reply.split()),30)
 def test_avatar_gender_and_voice_mode(self):
  self.assertEqual(voice_language('kokoro_hf_alpha_hindi'),'Hindi');self.assertEqual(voice_language('kokoro_hf_beta_hinglish'),'Hinglish')
  self.assertIn('लड़की',common_reply('aap ladke ho ya ladki','Hindi','feminine'))
  self.assertIn('लड़के',common_reply('aap ladke ho ya ladki','Hindi','masculine'))
  self.assertIsNone(common_reply('Delhi news','Hindi'))
 def test_devanagari_alone_is_not_quality(self):
  for text in ['सरल बातचीत के लिए आपका सहमति है।','मुझे प्रश्न या विचार देखने और उत्तर देने में बहुत अच्छा लगता है।','हां, अच्छा लगता है! आज गुणवत्ता के खेल में उम्मीद करते हैं।']:
   self.assertTrue(garbled_reply(text));self.assertFalse(LLM._matches_reply_language(text,'Hindi'))
 def test_other_conversation_still_generates_with_hindi_rules(self):
  with tempfile.TemporaryDirectory() as folder:
   model=LLM(Path(folder)/'memory.json',persist_memory=False);model.reply_language='Hindi'
   with patch.object(model,'_request',return_value='ज़रूर, पहले बताइए कि अपडेट कहाँ अटका है।') as request:
    self.assertIn('अपडेट',model.chat('mera update ruk gaya hai'))
    self.assertNotIn('sprinkle of mischief',request.call_args.args[0][0]['content'])
    self.assertTrue(any('Latin letters' in m['content'] for m in request.call_args.args[0] if m['role']=='system'))
if __name__=='__main__':unittest.main()
