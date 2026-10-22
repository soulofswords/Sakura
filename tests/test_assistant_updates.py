import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import numpy as np
from assistant_commands import run_command
from current_information import lookup
from stt import SpeechToText

class MicrophoneLanguageEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_voice_switch_changes_microphone_language_and_resamples(self):
        import io
        import soundfile as sf
        import app as server
        from starlette.datastructures import UploadFile,Headers
        recording=io.BytesIO();sf.write(recording,np.ones(48000,dtype=np.float32)*.02,48000,format='WAV')
        model=Mock();model.transcribe.return_value='नमस्ते'
        with tempfile.TemporaryDirectory() as folder:
            for voice,language in [('kokoro_hf_alpha_hindi','hi'),('kokoro_hf_beta_hinglish','hi'),('kokoro_af_heart','en')]:
                upload=UploadFile(file=io.BytesIO(recording.getvalue()),filename='test.wav',headers=Headers({'content-type':'audio/wav'}))
                with patch.object(server,'AUDIO_DIR',Path(folder)),patch.object(server,'stt',model),patch.object(server,'get_settings',return_value={'selected_voice':voice}):
                    result=await server.speech_to_text(upload)
                    self.assertEqual(result['text'],'नमस्ते')
                    samples,hint=model.transcribe.call_args.args
                    self.assertEqual(hint,language);self.assertEqual(len(samples),16000)


class AssistantUpdates(unittest.TestCase):
    def test_hindi_microphone_hint_transcribes_without_translation(self):
        stt=SpeechToText.__new__(SpeechToText);stt.model=Mock();stt.vad_available=True
        from types import SimpleNamespace
        stt.model.transcribe.return_value=([SimpleNamespace(text='नमस्ते, क्या तुम मुझे सुन सकती हो?',no_speech_prob=.1,avg_logprob=-.2)],None)
        text=stt._transcribe(np.ones(16000,dtype=np.float32)*.02,'hi')
        self.assertIn('नमस्ते',text)
        self.assertEqual(stt.model.transcribe.call_args.kwargs['language'],'hi')
        self.assertEqual(stt.model.transcribe.call_args.kwargs['task'],'transcribe')
        stt._transcribe(np.ones(16000,dtype=np.float32)*.02)
        self.assertIsNone(stt.model.transcribe.call_args.kwargs['language'],'System audio retains language detection')
    def test_short_app_alias_and_windows_registered_app(self):
        with tempfile.TemporaryDirectory() as directory:
            shortcut = Path(directory)/'OBS Studio.lnk'; shortcut.touch()
            with patch('assistant_commands.sys.platform','win32'), patch('assistant_commands.Path.rglob',return_value=[shortcut]), patch('assistant_commands.Path.is_dir',return_value=True), patch('assistant_commands.os.startfile',create=True) as launch:
                self.assertEqual(run_command('can you open OBS',True),'Opening obs.')
                launch.assert_called_once_with(str(shortcut.resolve()))
            registered=Mock(returncode=0,stdout='[{"Name":"Camera","AppID":"CameraPackage!App"}]')
            with patch('assistant_commands.sys.platform','win32'), patch('assistant_commands.Path.is_dir',return_value=False), patch('assistant_commands.subprocess.run',return_value=registered) as scan, patch('assistant_commands.os.startfile',create=True) as launch:
                self.assertEqual(run_command('open camera',True),'Opening camera.')
                launch.assert_called_once_with('shell:AppsFolder\\CameraPackage!App')
                self.assertNotIn('camera',scan.call_args.args[0][-1].lower(), 'User text never becomes PowerShell code')
                self.assertIn('could not find',run_command('open invented missing app',True))
                self.assertEqual(launch.call_count,1)

    def test_app_request_permission_and_exact_shortcut(self):
        with tempfile.TemporaryDirectory() as directory:
            shortcut = Path(directory)/'Discord.lnk'; shortcut.touch()
            with patch('assistant_commands.sys.platform','win32'), patch('assistant_commands.Path.rglob',return_value=[shortcut]), patch('assistant_commands.Path.is_dir',return_value=True), patch('assistant_commands.os.startfile',create=True) as launch:
                self.assertIn('Enable computer access',run_command('can you open Discord',False))
                launch.assert_not_called()
                self.assertEqual(run_command('can you open Discord',True),'Opening discord.')
                launch.assert_called_once_with(str(shortcut.resolve()))
                self.assertIn('could not find',run_command('open discord & calc',True))

    def test_noise_rejected_before_transcription(self):
        stt=SpeechToText.__new__(SpeechToText);stt.model=Mock();stt.vad_available=True
        audio=np.zeros(16000,dtype=np.float32);audio[40]=.8
        self.assertEqual(stt._transcribe(audio),'');stt.model.transcribe.assert_not_called()

    def test_vad_rejection_never_retries_without_filter(self):
        stt=SpeechToText.__new__(SpeechToText);stt.model=Mock();stt.vad_available=True
        stt.model.transcribe.return_value=([],None)
        self.assertEqual(stt._transcribe(np.ones(16000,dtype=np.float32)*.02),'')
        stt.model.transcribe.assert_called_once()
        self.assertTrue(stt.model.transcribe.call_args.kwargs['vad_filter'])
        self.assertIn('Delhi',stt.model.transcribe.call_args.kwargs['initial_prompt'])
        self.assertFalse(stt.model.transcribe.call_args.kwargs['condition_on_previous_text'])

    def test_confident_speech_passes(self):
        stt=SpeechToText.__new__(SpeechToText);stt.model=Mock();stt.vad_available=True
        stt.model.transcribe.return_value=([SimpleNamespace(text='Open Discord',no_speech_prob=.1,avg_logprob=-.2)],None)
        self.assertEqual(stt._transcribe(np.ones(16000,dtype=np.float32)*.02),'Open Discord')

    def test_weather_asks_location_and_labels_fresh_data(self):
        from datetime import datetime
        with patch('current_information.requests.get') as get, patch('current_information.datetime') as clock:
            clock.now.return_value=datetime(2026,10,13)
            self.assertIn('Which city',lookup('What is the weather?'));get.assert_not_called()
            geo=Mock();geo.json.return_value={'results':[{'name':'Delhi','country':'India','latitude':28,'longitude':77}]}
            forecast=Mock();forecast.json.return_value={'current':{'temperature_2m':30,'time':'2026-10-14T12:00'},'daily':{'time':['2026-10-14'],'temperature_2m_min':[20],'temperature_2m_max':[32],'precipitation_probability_max':[10]}}
            get.side_effect=[geo,forecast]
            reply=lookup('Weather in Delhi tomorrow?')
            self.assertIn('20 to 32 °C',reply);self.assertIn('Open-Meteo',reply);self.assertIn('2026-10-14',reply)

    def test_news_handles_network_failure_without_inventing(self):
        import requests
        with patch('current_information.requests.get',side_effect=requests.ConnectionError):
            self.assertIn('could not retrieve',lookup('Latest news about gaming'))
        self.assertIsNone(lookup('Hello there'))

if __name__=='__main__':unittest.main()
