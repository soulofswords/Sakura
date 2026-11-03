from pathlib import Path
from avatar_selection import request
from tts import polish_spoken_text


def test_speech_excludes_visual_tokens_and_url_paths():
    result=polish_spoken_text('[QUIET] Try this → [NVIDIA](https://www.nvidia.com/path?q=secret). Source: https://www.bbc.com/news/story?id=123')
    assert 'QUIET' not in result and '→' not in result and 'https' not in result and 'secret' not in result
    assert 'NVIDIA' in result and 'bbc.com' in result
    assert polish_spoken_text('[QUIET]')==''


def test_avatar_resolution_requires_explicit_unique_installed_model(tmp_path):
    folder=tmp_path/'pmx/Traditional Luka';folder.mkdir(parents=True);(folder/'Luka.pmx').write_bytes(b'fixture')
    assert request('Let\'s change your costume to Traditional Luka.',tmp_path)['avatar_model']=='pmx/Traditional Luka/Luka.pmx'
    assert request('change your costume to a traditional Chinese woman',tmp_path)['avatar_model']
    (folder/'Luka #2.pmx').write_bytes(b'fixture')
    assert 'avatar_picker' in request('change your costume to traditional',tmp_path)
    assert request('I changed your costume to Traditional Luka',tmp_path) is None
    assert 'avatar_picker' in request('change your costume to absent',tmp_path)


def test_avatar_conversational_outfit_requests_open_real_library(tmp_path):
    folder=tmp_path/'pmx/Miku universe/luka/Traditional';folder.mkdir(parents=True)
    (folder/'Luka.pmx').write_bytes(b'fixture')
    assert request("yea let's swap to a elegant one.",tmp_path)['avatar_picker']
    assert request('Okay, change it.',tmp_path)['avatar_picker']
    assert 'Luka' in request('what models are installed?',tmp_path)['reply']
    assert request('show cloud models',tmp_path)['avatar_cloud']
    assert request('change outfit to traditional from cloud',tmp_path)['avatar_cloud']
    assert request('switch to Teacher mode',tmp_path) is None
    assert request('change brightness to 50 percent',tmp_path) is None


def test_rvc_failed_result_never_reaches_the_wav_writer():
    from rvc_audio import require_audio
    import pytest
    with pytest.raises(RuntimeError,match='before producing audio'):require_audio(('private traceback',(None,None)))
    with pytest.raises(RuntimeError,match='no audio'):require_audio(None)
    class Audio: dtype='int16';size=100
    audio=Audio();assert require_audio(audio) is audio
