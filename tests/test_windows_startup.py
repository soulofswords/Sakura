from pathlib import Path
from unittest.mock import MagicMock
import sys

import windows_startup


def test_launcher_command_uses_installed_companion_and_quotes_spaces(tmp_path):
    base=tmp_path/'Sakura Companion/Sakura';base.mkdir(parents=True)
    launcher=tmp_path/'Sakura Companion.exe';launcher.write_bytes(b'launcher')
    assert windows_startup.command(base)=='"'+str(launcher)+'" --windows-startup'


def test_startup_toggle_sets_and_removes_only_sakura_current_user_entry(monkeypatch):
    registry=MagicMock();registry.HKEY_CURRENT_USER='current-user';registry.REG_SZ=1
    monkeypatch.setitem(sys.modules,'winreg',registry)
    monkeypatch.setattr(windows_startup,'command',lambda:'"Sakura Companion.exe"')
    import product
    monkeypatch.setattr(product,'EDITION','companion')
    registry.QueryValueEx.return_value=('"Sakura Companion.exe"',1)
    assert windows_startup.configure(True)['enabled']
    registry.SetValueEx.assert_called_once()
    assert registry.SetValueEx.call_args.args[1]=='Sakura Companion'
    assert registry.CreateKey.call_args_list[0].args==(registry.HKEY_CURRENT_USER,windows_startup.RUN_KEY)
    windows_startup.configure(False)
    assert registry.DeleteValue.call_count==2
    assert registry.DeleteValue.call_args.args[1]=='Sakura Companion'


def test_standard_installed_layout_uses_its_own_launcher(tmp_path):
    base=tmp_path/'Sakura';base.mkdir()
    launcher=tmp_path/'Sakura Companion.exe';launcher.write_bytes(b'launcher')
    assert windows_startup.command(base)=='"'+str(launcher)+'" --windows-startup'


def test_windows_disabled_entry_is_not_reported_as_enabled(monkeypatch):
    registry=MagicMock();registry.HKEY_CURRENT_USER='current-user'
    registry.QueryValueEx.side_effect=[('"Sakura Companion.exe" --windows-startup',1),(b'\x03\x00\x00\x00'+b'\x00'*8,3)]
    monkeypatch.setitem(sys.modules,'winreg',registry)
    result=windows_startup.status()
    assert result['registered'] and result['disabled_by_windows'] and not result['enabled']
