from unittest.mock import Mock

import pytest
import process_tools


def test_reused_pid_between_inspection_and_handle_is_never_terminated(monkeypatch):
    identity={'pid':12345,'name':'approved.exe','username':'owner','created':100.0}
    monkeypatch.setattr(process_tools,'inspect_target',lambda pid:identity)
    replacement=Mock();replacement.create_time.return_value=101.0
    monkeypatch.setattr(process_tools.psutil,'Process',lambda pid:replacement)
    with pytest.raises(ValueError,match='changed before termination'):
        process_tools.terminate(12345,identity)
    replacement.terminate.assert_not_called()


def test_the_inspected_process_handle_can_be_terminated(monkeypatch):
    identity={'pid':12345,'name':'approved.exe','username':'owner','created':100.0}
    monkeypatch.setattr(process_tools,'inspect_target',lambda pid:identity)
    target=Mock();target.create_time.return_value=100.0
    monkeypatch.setattr(process_tools.psutil,'Process',lambda pid:target)
    assert process_tools.terminate(12345,identity)['stopped']
    target.terminate.assert_called_once()
    target.wait.assert_called_once_with(timeout=3)
