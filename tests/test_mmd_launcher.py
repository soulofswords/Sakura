from unittest.mock import patch
import pytest
from mmd_launcher import find_mmd,open_mmd


def test_mmd_requires_complete_selected_install_and_launches_without_shell(tmp_path):
    exe=tmp_path/'MikuMikuDance.exe';exe.write_bytes(b'fixture')
    assert find_mmd(str(exe)) is None
    (tmp_path/'Data').mkdir();assert find_mmd(str(tmp_path))==exe
    with patch('mmd_launcher.subprocess.Popen') as launch:
        assert open_mmd(str(exe))['opened']
        assert launch.call_args.args[0]==[str(exe)]
        assert launch.call_args.kwargs['cwd']==str(tmp_path)
        assert not launch.call_args.kwargs.get('shell')
