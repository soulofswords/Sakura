import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from config import VOICE_PRESETS, voice_language
from llm import LLM
from tts import TextToSpeech


class VoiceCatalogTests(unittest.TestCase):
    def test_ten_english_voices_per_gender_and_two_language_choices(self):
        for gender in ('Male', 'Female'):
            voices = [p for p in VOICE_PRESETS if p.get('gender') == gender and p['language'] == 'English']
            self.assertEqual(len(voices), 10)
            self.assertTrue(all(p['backend']=='kokoro' for p in voices))
            self.assertEqual(len({p['voice'] for p in voices}), 10)
        self.assertEqual(voice_language('swara_hindi'), 'Hindi')
        self.assertEqual(voice_language('neerja_hinglish'), 'Hinglish')
        self.assertEqual(voice_language('rvc_some_imported_voice'), 'English')
        self.assertFalse(any(p['voice'].startswith('ja-') for p in VOICE_PRESETS))

    def test_language_selection_reaches_gemini_and_summary_is_unmodified(self):
        with tempfile.TemporaryDirectory() as folder:
            model = LLM(Path(folder) / 'memory.json')
            model.provider = 'gemini'
            for language in ('English', 'Hindi', 'Hinglish'):
                model.reply_language = language
                with patch.object(model, '_request_gemini', return_value='test') as request:
                    model._request([{'role': 'user', 'content': 'Namaste'}])
                    sent = request.call_args_list[0].args[0]
                    language_rules = [m['content'] for m in sent if m['role'] == 'system'
                                      and 'Selected speech language:' in m['content']]
                    self.assertEqual(len(language_rules), 1)
                    self.assertIn(language, language_rules[0])
                    self.assertIn('overrides', language_rules[0])
                    self.assertEqual(sent[-1], {'role': 'user', 'content': 'Namaste'})
            with patch.object(model, '_request_gemini', return_value='test') as request:
                messages = [{'role': 'user', 'content': 'Summarize facts'}]
                model._request(messages, summarizing=True)
                self.assertEqual(request.call_args.args[0], messages)

    def test_rvc_uses_english_base_after_hindi(self):
        voice = TextToSpeech()
        voice.set_voice_preset('swara_hindi')
        voice.set_voice_preset('rvc_test')
        self.assertTrue(voice.current_voice=='af_heart')
        voice.set_voice_preset('nanami_japanese')
        self.assertEqual(voice.current_voice, 'bf_alice')

    def test_wrong_language_gets_one_correction_only(self):
        with tempfile.TemporaryDirectory() as folder:
            model=LLM(Path(folder)/'memory.json')
            for language,corrected in [('Hindi','हाँ मास्टर, मैं आपकी मदद कर सकती हूँ।'),('Hinglish','Haan Master, main aapki help kar sakti hoon.')]:
                model.reply_language=language
                with patch.object(model,'_request_raw',side_effect=['Hello, how can I help you?',corrected]) as request:
                    self.assertEqual(model._request([{'role':'user','content':'hello'}]),corrected)
                    self.assertEqual(request.call_count,2)
                    self.assertIn('Rewrite',request.call_args.args[0][0]['content'])
                with patch.object(model,'_request_raw',return_value=corrected) as request:
                    model._request([{'role':'user','content':'hello'}]);self.assertEqual(request.call_count,1)
                with patch.object(model,'_request_raw',return_value='[QUIET]') as request:
                    self.assertEqual(model._request([]),'[QUIET]');self.assertEqual(request.call_count,1)
            with patch.object(model,'_request_raw',return_value='Still English') as request:
                model._request([]);self.assertEqual(request.call_count,2,'No unbounded retries')


if __name__ == '__main__':
    unittest.main()
