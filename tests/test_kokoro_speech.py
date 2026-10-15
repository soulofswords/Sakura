import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import numpy as np
import app as server
import kokoro_speech as runtime
from tts import TextToSpeech
from voice_catalog import canonical_voice_id,DEFAULT_VOICE_ID,VOICE_PRESETS


class KokoroSpeechTests(unittest.TestCase):
    def test_saved_voice_migration_preserves_other_preferences(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(server,'SETTINGS_FILE',Path(folder)/'settings.json'):
            server.SETTINGS_FILE.write_text(json.dumps({'selected_voice':'emma_energetic','assistant_name':'Myra','physics_wind':.4}),encoding='utf-8')
            settings=server.get_settings()
            self.assertEqual(settings['selected_voice'],'kokoro_af_bella');self.assertEqual(settings['assistant_name'],'Myra');self.assertEqual(settings['physics_wind'],.4)
            self.assertEqual(canonical_voice_id('en-US-AvaNeural'),DEFAULT_VOICE_ID)
            self.assertEqual(canonical_voice_id('unknown-online-voice'),DEFAULT_VOICE_ID)
            self.assertEqual(canonical_voice_id('rvc_miku'),'rvc_miku')

    def test_language_rate_audio_and_invalid_output(self):
        engine=Mock();engine.create.return_value=(np.ones(2400,dtype=np.float32)*.1,24000)
        with tempfile.TemporaryDirectory() as folder,patch.object(runtime,'prepare'),patch.object(runtime,'_engine',engine):
            path=Path(folder)/'test.wav'
            runtime.render_speech('Hello',path,voice='af_heart',rate='+25%')
            self.assertEqual(engine.create.call_args.kwargs['speed'],1.25);self.assertEqual(engine.create.call_args.kwargs['lang'],'en-us')
            self.assertEqual(path.read_bytes()[:4],b'RIFF')
            runtime.render_speech('नमस्ते',path,voice='hf_alpha',language='Hindi')
            self.assertEqual(engine.create.call_args.kwargs['lang'],'hi')
            engine.create.return_value=(np.array([np.nan]),24000)
            with self.assertRaisesRegex(RuntimeError,'invalid speech'):runtime.render_speech('Hello',path)
            self.assertFalse(path.exists())

    def test_assets_are_integrity_checked_before_use(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(runtime,'ASSETS_DIR',Path(folder)),patch.object(runtime,'ASSETS',{'test.bin':(3,'invalid-checksum')}),patch('requests.get',side_effect=RuntimeError('Download prohibited')):
            (Path(folder)/'test.bin').write_bytes(b'bad')
            with self.assertRaisesRegex(RuntimeError,'Download prohibited'):runtime.ensure_assets()

    def test_installer_contains_speech_assets_without_imported_character_or_rvc_models(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('kokoro_builder','tools/build-installers.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        names=[name for _,name in builder.app_files()]
        self.assertIn('Sakura/kokoro-assets/kokoro-v1.0.int8.onnx',names)
        self.assertIn('Sakura/kokoro-assets/voices-v1.0.bin',names)
        self.assertFalse(any(name.startswith(('Sakura/models/','Sakura/voices/')) for name in names))

    def test_tracking_product_can_prepare_local_chat_reader_speech_but_not_ai(self):
        from fastapi.testclient import TestClient
        previous=getattr(server.app.state,'tracking_only',False)
        server.app.state.tracking_only=True
        try:
            with patch.object(server,'EDITION','vtuber'),patch.object(runtime,'status',return_value={'phase':'ready'}),patch.object(runtime,'prepare',return_value={'phase':'ready'}):
                client=TestClient(server.app)
                self.assertEqual(client.get('/api/tts/kokoro').status_code,200)
                self.assertEqual(client.post('/api/tts/kokoro').status_code,200)
                self.assertEqual(client.post('/api/chat',json={'text':'hello'}).status_code,409)
                self.assertEqual(client.post('/api/tts/speak',json={'text':'hello'}).status_code,409)
        finally:server.app.state.tracking_only=previous


if __name__=='__main__':unittest.main()
