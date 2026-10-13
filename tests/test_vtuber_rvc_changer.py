import tempfile
import unittest
import sys
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
import app


class VtuberRvcChangerTests(unittest.TestCase):
    def setUp(self):
        app.app.state.tracking_only = True

    def tearDown(self):
        app.app.state.tracking_only = False

    def test_conversion_requires_tracking_mode_and_selected_rvc_voice(self):
        client = TestClient(app.app)
        audio = {'audio': ('microphone.wav', b'RIFF test', 'audio/wav')}
        app.app.state.tracking_only = False
        self.assertEqual(client.post('/api/voice-changer/convert', files=audio).status_code, 409)
        app.app.state.tracking_only = True
        with patch.object(app, 'tts', Mock(rvc_model=None, selected_preset_id='sakura_ava')):
            response = client.post('/api/voice-changer/convert', files=audio)
        self.assertEqual(response.status_code, 409)

    def test_converted_audio_is_returned_and_temporary_files_are_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            audio_dir = Path(folder)
            voice = Mock(rvc_model='voices/miku/model.pth', selected_preset_id='rvc_miku')

            def convert(source):
                output = audio_dir / 'converted.wav'
                self.assertEqual(Path(source).read_bytes(), b'RIFF microphone sample')
                output.write_bytes(b'RIFF converted sample')
                return str(output)

            voice._apply_rvc_conversion.side_effect = convert
            with patch.object(app, 'AUDIO_DIR', audio_dir), patch.object(app, 'tts', voice):
                response = TestClient(app.app).post('/api/voice-changer/convert', files={
                    'audio': ('microphone.wav', b'RIFF microphone sample', 'audio/wav')
                })
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.content, b'RIFF converted sample')
            self.assertEqual(response.headers['content-type'], 'audio/wav')
            self.assertEqual(list(audio_dir.iterdir()), [])
            voice._apply_rvc_conversion.assert_called_once()

    def test_builtin_voice_mode_transcribes_locally_and_speaks_selected_voice(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'builtin.mp3'
            class Voice:
                selected_preset_id = 'sakura_ava'
                def __copy__(self): return self
                def set_voice_preset(self, preset): self.selected_preset_id = preset
                def set_rvc_model(self, model): self.rvc_model = model
                async def speak_to_file_async(self, text):
                    self.transcript = text
                    output.write_bytes(b'built-in speech')
                    return str(output)

            class Recognizer:
                def transcribe(self, samples):
                    self.sample_count = len(samples)
                    return 'Hello Sakura'

            soundfile = SimpleNamespace(read=lambda *_args, **_kwargs: (
                __import__('numpy').ones(1600, dtype='float32'), 16000))
            voice = Voice()
            recognizer = Recognizer()
            with patch.object(app, 'AUDIO_DIR', Path(folder)), \
                    patch.object(app, 'tts', voice), patch.object(app, 'stt', recognizer), \
                    patch.dict(sys.modules, {'soundfile': soundfile}):
                response = TestClient(app.app).post('/api/voice-changer/speak', files={
                    'audio': ('microphone.wav', b'WAV test data', 'audio/wav')
                })
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.content, b'built-in speech')
            self.assertEqual(response.headers['content-type'], 'audio/mpeg')
            self.assertEqual(voice.transcript, 'Hello Sakura')
            self.assertEqual(voice.selected_preset_id, 'sakura_ava')
            self.assertIsNone(voice.rvc_model)
            self.assertEqual(recognizer.sample_count, 1600)
            self.assertFalse(output.exists(), 'generated speech should be cleaned up after response')


if __name__ == '__main__':
    unittest.main()
