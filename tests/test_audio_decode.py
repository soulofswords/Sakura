import io
from unittest.mock import patch
import numpy as np
import pytest
import soundfile as sf
from audio_decode import decode_audio


def wav(seconds=1):
    output=io.BytesIO();sf.write(output,np.zeros(44100*seconds,dtype='float32'),44100,format='WAV');return output.getvalue()


def test_bundled_decoder_resamples_without_cli_and_enforces_duration():
    assert decode_audio(wav()).shape==(16000,)
    with pytest.raises(ValueError,match='at most'):decode_audio(wav(2),max_seconds=1)
    with pytest.raises(ValueError):decode_audio(b'invalid')


def test_voice_memo_works_when_ffmpeg_is_not_installed():
    from agent_voice import transcribe
    with patch('agent_voice.shutil.which',return_value=None):
        assert transcribe(wav(),lambda audio:'decoded '+str(audio.size))=='decoded 16000'


def test_browser_webm_is_decoded_without_an_external_program():
    import av
    output=io.BytesIO()
    with av.open(output,'w',format='webm') as container:
        stream=container.add_stream('libopus',rate=48000)
        frame=av.AudioFrame.from_ndarray(np.zeros((1,48000),dtype='float32'),format='fltp',layout='mono');frame.sample_rate=48000
        for packet in stream.encode(frame):container.mux(packet)
        for packet in stream.encode(None):container.mux(packet)
    content=output.getvalue()
    assert content.startswith(b'\x1a\x45\xdf\xa3')
    assert decode_audio(content).shape==(16000,)
