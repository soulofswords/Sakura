import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import wave

from desktop_wake import DesktopWake, phrase_words

BASE=Path(__file__).resolve().parents[1]

class DesktopWakeTests(unittest.TestCase):
    def test_phrase_validation(self):
        self.assertEqual(phrase_words('Hey Sakura'),'hey sakura')
        self.assertEqual(phrase_words('Hello Computer'),'hello computer')
        for value in ['hello','hi 123','one two three four five six seven','']:
            with self.assertRaises(ValueError):phrase_words(value)

    def test_optional_default_and_missing_pack(self):
        with tempfile.TemporaryDirectory() as directory:
            wake=DesktopWake(directory,lambda text:None)
            self.assertFalse(wake.state()['enabled'])
            self.assertFalse(wake.state()['installed'])
            self.assertFalse(wake.root.exists(),'No silent pack download or file creation')
            with self.assertRaises(RuntimeError):wake.start('hey sakura')

    def test_tampered_download_rejected(self):
        with tempfile.TemporaryDirectory() as directory,patch('urllib.request.urlopen',return_value=io.BytesIO(b'bad data')):
            wake=DesktopWake(directory,lambda text:None)
            with self.assertRaisesRegex(RuntimeError,'integrity'):wake.install()
            self.assertFalse(wake.state()['installed'])
            self.assertFalse(list(wake.root.glob('*.download')))

    @unittest.skipUnless((BASE/'tools/android-cache/wake-deps/model.zip').is_file() and (BASE/'audit-results/wake-command.wav').is_file(),'Optional cached test packs/synthetic audio unavailable')
    def test_real_offline_model_without_microphone(self):
        cache=BASE/'tools/android-cache/wake-deps'
        def download(url,**kwargs):return (cache/('model.zip' if url.endswith('model-small-en-us-0.15.zip') else 'vosk-win.whl')).open('rb')
        with tempfile.TemporaryDirectory() as directory,patch('urllib.request.urlopen',side_effect=download):
            commands=[];wake=DesktopWake(directory,lambda text:commands.append(text),lambda message:print(message,flush=True))
            wake.install();self.assertTrue(wake.state()['installed'])
            library=wake._library;wake._library=lambda:library(cache/'win')
            recordings=['wake-positive.wav','wake-command.wav']
            class FakeInput:
                def __init__(self,**kwargs):
                    with wave.open(str(BASE/'audit-results'/recordings.pop(0)),'rb') as wav:self.audio=b'\0'*320000+wav.readframes(wav.getnframes())+b'\0'*96000
                    self.offset=0
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def read(self,n):
                    piece=self.audio[self.offset:self.offset+n*2];self.offset+=n*2
                    return piece.ljust(n*2,b'\0'),False
            def received(text):commands.append(text);wake.cancel.set()
            wake.on_command=received
            # No actual sounddevice recording or microphone permissions are used.
            with patch.dict('sys.modules',sounddevice=types.SimpleNamespace(RawInputStream=FakeInput)),patch('winsound.Beep'):
                wake.start('hey sakura');wake.thread.join(20)
            self.assertFalse(wake.thread.is_alive())
            self.assertEqual(commands,['what time is it'])
            self.assertFalse(wake.recording.is_set())
            # No wake phrase at all: filler and unrelated speech cannot open a command turn.
            for audio_name in ['wake-huh.wav','wake-negative.wav']:
                recordings[:]=[audio_name];commands.clear();wake.busy=False
                class NegativeInput(FakeInput):
                    def read(self,n):
                        result=super().read(n)
                        if self.offset>len(self.audio):wake.cancel.set()
                        return result
                with patch.dict('sys.modules',sounddevice=types.SimpleNamespace(RawInputStream=NegativeInput)),patch('winsound.Beep'):
                    wake.start('hey sakura');wake.thread.join(8)
                self.assertFalse(wake.thread.is_alive())
                self.assertEqual(commands,[],audio_name+' must not activate or send a request')


if __name__=='__main__':unittest.main()
