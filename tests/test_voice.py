import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
import requests
import app
from tts import TextToSpeech
from tts import polish_spoken_text
from config import VOICE_PRESETS

PRESETS=[p for p in VOICE_PRESETS if p['voice']!='rvc']
def voice():
    tts=TextToSpeech.__new__(TextToSpeech)
    tts.backend='kokoro';tts.rvc_model=None;tts.rvc_index=None
    tts.rvc_pitch=0;tts.rvc_index_rate=0.75
    tts.set_voice_preset(PRESETS[0]['id'])
    return tts

class VoiceTests(unittest.TestCase):
    def test_spoken_text_removes_decoration_preserves_language_and_numbers(self):
        text = '🌸 **Hello!!** How are you~?\n- तापमान 25°C है। Use [Python](https://python.org) at 3.5 GHz.'
        self.assertEqual(polish_spoken_text(text), 'Hello! How are you? तापमान 25°C है। Use Python at 3.5 GHz.')
    def test_selected_voice_is_respected_for_all_languages(self):
        tts=voice();tts.set_voice_preset(PRESETS[1]['id'])
        for text in ['Hello there','haan kya hai yaar','नमस्ते कैसे हो']:
            self.assertEqual(tts._pick_voice(text),PRESETS[1]['voice'])
        self.assertEqual(tts.current_rate,PRESETS[1]['rate'])
        tts.rvc_model='old.pth';tts.rvc_index='old.index'
        tts.set_voice_preset(PRESETS[0]['id'])
        self.assertIsNone(tts.rvc_model);self.assertIsNone(tts.rvc_index)

    def test_audio_urls_are_unique(self):
        tts=voice()
        with patch('kokoro_speech.render_speech',side_effect=lambda text,path,**kwargs:str(path)) as render:
            first=asyncio.run(tts._generate_kokoro_async('hello'))
            second=asyncio.run(tts._generate_kokoro_async('hello'))
            self.assertNotEqual(first,second)
            self.assertEqual(render.call_args.kwargs['voice'],tts.current_voice)

    def test_inflight_speech_keeps_its_voice(self):
        async def scenario():
            tts=voice();entered=asyncio.Event();release=asyncio.Event();used=[]
            async def generate(snapshot,text):
                used.append(snapshot.current_voice);entered.set();await release.wait()
                used.append(snapshot.current_voice);return 'sample.mp3'
            with patch.object(TextToSpeech,'_generate_kokoro_async',generate):
                task=asyncio.create_task(tts.speak_to_file_async('hello'))
                await entered.wait();tts.set_voice_preset(PRESETS[1]['id']);release.set();await task
                self.assertEqual(used,[PRESETS[0]['voice']]*2)
                self.assertEqual(tts.current_voice,PRESETS[1]['voice'])
        asyncio.run(scenario())

    def test_preview_cannot_restore_old_voice_over_new_selection(self):
        async def scenario():
            active=voice();entered=asyncio.Event();release=asyncio.Event()
            async def generate(snapshot,text):
                entered.set();await release.wait();return 'sample.mp3'
            with patch.object(app,'tts',active),patch.object(TextToSpeech,'_generate_kokoro_async',generate):
                task=asyncio.create_task(app.test_tts_voice({'voice':PRESETS[0]['id']}))
                await entered.wait();active.set_voice_preset(PRESETS[1]['id']);release.set();await task
                self.assertEqual(active.current_voice,PRESETS[1]['voice'])
        asyncio.run(scenario())

    def test_rvc_offline_is_reported_instead_of_fake_character_voice(self):
        tts=voice();tts.rvc_model='miku.pth'
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'audio.mp3';path.write_bytes(b'test')
            with patch('rvc_manager.ensure_rvc_service'), patch('requests.post',side_effect=requests.ConnectionError()):
                with self.assertRaisesRegex(RuntimeError,'RVC voice converter is unavailable'):
                    tts._apply_rvc_conversion(str(path))

if __name__=='__main__': unittest.main()
