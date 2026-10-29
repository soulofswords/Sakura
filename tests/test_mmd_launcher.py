from unittest.mock import patch
import pytest
from mmd_launcher import find_mmd,open_mmd,_drop_payload,_model_window
import struct


def test_mmd_requires_complete_selected_install_and_launches_without_shell(tmp_path):
    exe=tmp_path/'MikuMikuDance.exe';exe.write_bytes(b'fixture')
    assert find_mmd(str(exe)) is None
    (tmp_path/'Data').mkdir();assert find_mmd(str(tmp_path))==exe
    model=tmp_path/'model.pmx';model.write_bytes(b'PMX ')
    with patch('mmd_launcher.subprocess.Popen') as launch,patch('pmx_editor.model_file',return_value=model),patch('mmd_launcher._model_window',return_value=123),patch('mmd_launcher._send_model_drop') as drop:
        assert open_mmd(str(exe),'pmx/model.pmx')['import_requested']
        assert launch.call_args.args[0]==[str(exe)]
        assert launch.call_args.kwargs['cwd']==str(tmp_path)
        assert not launch.call_args.kwargs.get('shell')
        drop.assert_called_once_with(123,model)


def test_drop_payload_preserves_unicode_spaces_and_texture_directory():
    path='F:/models/ミク outfit/model.pmx'
    content=_drop_payload(path)
    assert struct.unpack('<IiiII',content[:20])==(20,0,0,0,1)
    assert content[20:].decode('utf-16-le')==path+'\0\0'


def test_invalid_model_never_starts_mmd():
    with patch('mmd_launcher.subprocess.Popen') as launch:
        with pytest.raises(ValueError):open_mmd('MikuMikuDance.exe','../../secret.pmx')
        launch.assert_not_called()


def test_early_exit_is_not_reported_as_loaded():
    from unittest.mock import Mock
    with pytest.raises(RuntimeError,match='exited'):_model_window(Mock(poll=lambda:1))
