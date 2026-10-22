import unittest
from unittest.mock import Mock,patch,AsyncMock
from spoken_text import strip_speech_decoration
from tts import polish_spoken_text
from tests.test_voice import voice
import app as server

class SpeechDecorationTests(unittest.TestCase):
 def test_reported_trailing_emoji_and_quote_marks(self):
  text='😂 Okay, okay — here we go: > “You tapped my chest…” > “Nope!” (And if you’re not laughing yet — I’ll keep going until you do. 🐱💥)'
  cleaned=polish_spoken_text(text)
  for token in ['😂','🐱','💥','>'] :self.assertNotIn(token,cleaned)
  self.assertIn('You tapped my chest',cleaned)
 def test_emoji_sequences_do_not_leave_spoken_fragments(self):
  self.assertEqual(polish_spoken_text('Hello 🐱💥 🇮🇳 👩🏽‍💻 1️⃣ ▶️ 🏳️‍🌈!'),'Hello!')
  self.assertEqual(polish_spoken_text('🐱💥 🇮🇳 1️⃣'),'')
  self.assertEqual(polish_spoken_text('नमस्ते 😄! तापमान 25°C है। 5 > 2. Use 2*3.'),'नमस्ते! तापमान 25°C है। 5 > 2. Use 2 times 3.')

class SpeechBoundaryTests(unittest.IsolatedAsyncioTestCase):
 async def test_backend_filters_before_synthesis(self):
  speaker=voice()
  with patch.object(type(speaker),'_generate_kokoro_async',new=AsyncMock(return_value='voice.wav')) as generate:
   await speaker.speak_to_file_async('Hello 🐱💥!')
   generate.assert_awaited_once_with('Hello!')
   generate.reset_mock();self.assertIsNone(await speaker.speak_to_file_async('🐱💥'));generate.assert_not_awaited()
 async def test_deferred_api_preserves_chat_but_cleans_speech(self):
  model=Mock();model.chat.return_value='Hello 🐱💥!'
  with patch.object(server,'llm',model),patch.object(server,'get_settings',return_value={}),patch('assistant_commands.run_command',return_value='Hello 🐱💥!'),patch('current_information.lookup_with_context',return_value=(None,None)):
   result=await server.chat({'text':'say hello','defer_audio':True})
  self.assertEqual(result['reply'],'Hello 🐱💥!');self.assertEqual(result['speech_reply'],'Hello!')

if __name__=='__main__':unittest.main()
