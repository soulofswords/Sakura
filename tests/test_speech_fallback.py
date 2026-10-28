import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
import app as server
import tts as speech
from system_speech import render_system_speech
from tts import TextToSpeech, speech_notice


class SpeechFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_offline_selection_uses_exact_installed_voice_and_never_edge(self):
        choices=[{'id':'system_en_zira','system_name':'Microsoft Zira','gender':'Female','language':'English'},
                 {'id':'system_en_heera','system_name':'Microsoft Heera','gender':'Female','language':'English'}]
        voice=TextToSpeech()
        with patch('system_speech.system_voice_presets',return_value=choices), patch('system_speech.render_system_speech',return_value='response_offline_test.wav') as native, patch('kokoro_speech.render_speech') as kokoro:
            for selected in choices:
                voice.set_voice_preset(selected['id'])
                await voice.speak_to_file_async('Hello')
                self.assertEqual(native.call_args.kwargs['voice'],selected['system_name'])
            kokoro.assert_not_called()
            self.assertIsNone(speech_notice('response_offline_test.wav'))

    async def test_local_runtime_error_is_reported_without_switching_to_a_different_voice(self):
        voice=TextToSpeech()
        with patch('kokoro_speech.render_speech',side_effect=RuntimeError('Kokoro files are not ready')), patch.object(voice,'_generate_system') as system:
            with self.assertRaisesRegex(RuntimeError,'Kokoro files are not ready'):
                await voice.speak_to_file_async('Hello')
            system.assert_not_called()

    async def test_fallback_still_passes_through_rvc_and_preserves_gender_language(self):
        voice=TextToSpeech();voice.set_voice_preset('swara_hindi')
        with patch('system_speech.render_system_speech',return_value='system.wav') as native:
            self.assertEqual(voice._generate_system('नमस्ते'),'system.wav')
            self.assertEqual(native.call_args.kwargs['language'],'Hindi')
            self.assertEqual(native.call_args.kwargs['gender'],'Female')
        male=next(p for p in speech.VOICE_PRESETS if p['gender']=='Male')
        voice.set_voice_preset(male['id'])
        with patch('system_speech.render_system_speech',return_value='system.wav') as native:
            voice._generate_system('Hello')
            self.assertEqual(native.call_args.kwargs['gender'],'Male')
        voice.set_voice_preset('rvc_custom');voice.rvc_model='test.pth'
        with patch.object(TextToSpeech,'_generate_kokoro_async',AsyncMock(return_value='response_system_test.wav')), patch.object(TextToSpeech,'_apply_rvc_conversion',return_value='rvc.wav') as convert:
            self.assertEqual(await voice.speak_to_file_async('Hello'),'rvc.wav')
            convert.assert_called_once_with('response_system_test.wav')

    async def test_api_reports_working_fallback_without_websocket_url(self):
        voice=Mock();voice.speak_to_file_async=AsyncMock(return_value='response_system_test.wav')
        with patch.object(server,'tts',voice):
            result=await server.generate_reply_speech({'text':'Hello'})
        self.assertEqual(result['audio'],'/audio/response_system_test.wav')
        self.assertIsNone(result['voice_notice'])
        self.assertNotIn('wss://',str(result))
        self.assertIsNone(speech_notice('response_regular.mp3'))

    async def test_offline_selection_saves_and_restores_through_settings_api(self):
        from local_client import TestClient
        choices=[{'id':'system_en_zira','system_name':'Microsoft Zira','gender':'Female','language':'English'},
                 {'id':'system_en_heera','system_name':'Microsoft Heera','gender':'Female','language':'English'}]
        voice=TextToSpeech()
        with tempfile.TemporaryDirectory() as folder, patch.object(server,'SETTINGS_FILE',Path(folder)/'settings.json'), patch.object(server,'tts',voice), patch.object(server,'llm',None), patch.object(server,'sync_selected_rvc_service',AsyncMock()), patch('system_speech.system_voice_presets',return_value=choices):
            client=TestClient(server.app)
            for selected in choices:
                response=client.post('/api/settings',json={'selected_voice':selected['id']})
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(voice.selected_preset_id,selected['id'])
                self.assertEqual(client.get('/api/settings').json()['selected_voice'],selected['id'])
            fresh=TextToSpeech();fresh.set_voice_preset(server.get_settings()['selected_voice'])
            with patch('system_speech.render_system_speech',return_value='response_offline_test.wav') as native:
                await fresh.speak_to_file_async('Hello')
                self.assertEqual(native.call_args.kwargs['voice'],'Microsoft Heera')
            self.assertEqual(client.post('/api/settings',json={'selected_voice':'system_en_missing'}).status_code,400)
            self.assertEqual(server.get_settings()['selected_voice'],'system_en_heera')


class SystemSpeechTests(unittest.TestCase):
    def test_text_is_data_and_failed_output_is_deleted(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'speech.wav';out.write_bytes(b'partial')
            text='Hello $(Get-Process); "quoted" नमस्ते'
            with patch('system_speech.sys.platform','win32'), patch('system_speech.subprocess.CREATE_NO_WINDOW', 0, create=True), patch('system_speech.subprocess.run',return_value=Mock(returncode=1)) as process:
                with self.assertRaisesRegex(RuntimeError,'Windows Hindi female voice'):
                    render_system_speech(text,out,language='Hindi')
            self.assertEqual(json.loads(process.call_args.kwargs['input'])['text'],text)
            self.assertNotIn(text,str(process.call_args.args[0]),'Spoken text must never be interpolated into shell code')
            self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
