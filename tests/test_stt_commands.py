import threading,unittest
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
from stt import SpeechToText
class RecognitionTests(unittest.TestCase):
 def recognizer(self,text,score=-.5,silence=.02):
  stt=SpeechToText.__new__(SpeechToText);stt._transcribe_lock=threading.RLock();stt.vad_available=True
  stt.model=Mock();stt.model.transcribe.return_value=([SimpleNamespace(text=text,avg_logprob=score,no_speech_prob=silence,compression_ratio=1)],SimpleNamespace())
  return stt
 def test_command_hints_and_explicit_language(self):
  stt=self.recognizer('Delhi News.');audio=np.sin(np.arange(16000)*.2).astype(np.float32)*.1
  self.assertEqual(stt.transcribe(audio,'en'),'Delhi News.')
  options=stt.model.transcribe.call_args.kwargs
  self.assertEqual(options['language'],'en');self.assertEqual(options['temperature'],0);self.assertFalse(options['condition_on_previous_text']);self.assertIn('Delhi',options['initial_prompt']);self.assertIn('Mumbai',options['initial_prompt'])
  stt.transcribe(audio,'hi');self.assertEqual(stt.model.transcribe.call_args.kwargs['language'],'hi')
 def test_uncertain_short_phrase_requires_repeat(self):
  audio=np.sin(np.arange(16000)*.2).astype(np.float32)*.1
  for text,score,silence in [('The Lineos',-.91,.2),('Belly News',-.76,.45),('hello',-.2,.8)]:
   self.assertEqual(self.recognizer(text,score,silence).transcribe(audio,'en'),'')
 def test_silence_never_generates_prompt_words(self):
  stt=self.recognizer('Delhi news');self.assertEqual(stt.transcribe(np.zeros(16000,dtype=np.float32),'en'),'');stt.model.transcribe.assert_not_called()
if __name__=='__main__':unittest.main()
