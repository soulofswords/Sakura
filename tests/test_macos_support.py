"""Platform boundary regressions; actual Apple API execution needs a Mac."""
from pathlib import Path
from unittest.mock import Mock
import sys
import pytest
import gpu_info
import ollama_runtime
import rvc_manager
import credentials
import owned_process
import assistant_commands


def test_apple_gpu_detection_never_runs_windows_queries(monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'darwin')
    monkeypatch.setattr(gpu_info.platform, 'machine', lambda: 'arm64')
    monkeypatch.setattr(gpu_info, '_video_controller_names', lambda: pytest.fail('Windows GPU query on Mac'))
    gpu_info.detect_gpu.cache_clear()
    try:
        assert gpu_info.detect_gpu()['vendor'] == 'apple'
    finally:
        gpu_info.detect_gpu.cache_clear()


def test_apple_does_not_enable_windows_vulkan():
    assert 'OLLAMA_VULKAN' not in ollama_runtime.build_ollama_env({}, 'apple', True)


def test_mac_ollama_does_not_pick_windows_exe(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'platform', 'darwin')
    monkeypatch.setattr(ollama_runtime, 'BASE_DIR', tmp_path)
    (tmp_path / 'ollama-runtime').mkdir()
    (tmp_path / 'ollama-runtime' / 'ollama.exe').touch()
    monkeypatch.setattr(ollama_runtime.shutil, 'which', lambda _: '/opt/homebrew/bin/ollama')
    assert ollama_runtime._bundled_executable() == '/opt/homebrew/bin/ollama'


def test_mac_rvc_uses_native_interpreter(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'platform', 'darwin')
    monkeypatch.setattr(rvc_manager, 'BASE', tmp_path)
    root = tmp_path / 'rvc-mac-runtime'
    (root / 'bin').mkdir(parents=True)
    (root / 'bin' / 'python').touch()
    (root / 'lib' / 'python3.10' / 'site-packages' / 'torch').mkdir(parents=True)
    assert rvc_manager._runtime_python() == root / 'bin' / 'python'


def test_mac_rvc_missing_reports_setup(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'platform', 'darwin')
    monkeypatch.setattr(rvc_manager, 'BASE', tmp_path)
    with pytest.raises(RuntimeError, match='setup-rvc-macos.command'):
        rvc_manager._runtime_python()


def test_mac_keychain_roundtrip_never_reads_windows_key(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'platform', 'darwin')
    key = tmp_path / '.gemini-key.bin'
    key.write_bytes(b'Windows encrypted data')
    monkeypatch.setattr(credentials, 'KEY_FILE', key)
    store = {}
    backend = Mock()
    backend.get_password.side_effect = lambda service, user: store.get((service, user))
    backend.set_password.side_effect = lambda service, user, value: store.update({(service, user): value})
    backend.delete_password.side_effect = lambda service, user: store.pop((service, user))
    monkeypatch.setattr(credentials, '_mac_keyring', lambda: backend)
    assert credentials.get_gemini_key() == ''
    credentials.set_gemini_key('synthetic-test-key')
    assert credentials.get_gemini_key() == 'synthetic-test-key'
    credentials.set_gemini_key('')
    assert credentials.get_gemini_key() == ''
    assert key.read_bytes() == b'Windows encrypted data'


def test_mac_keychain_failure_is_handled_as_oserror(monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'darwin')
    backend = Mock()
    backend.get_password.side_effect = RuntimeError('locked keychain')
    monkeypatch.setattr(credentials, '_mac_keyring', lambda: backend)
    with pytest.raises(OSError, match='Keychain'):
        credentials.get_gemini_key()


def test_posix_owned_job_never_kills_parent_group(monkeypatch):
    monkeypatch.setattr(owned_process.os, 'name', 'posix')
    monkeypatch.setattr(owned_process.os, 'getpgid', lambda pid: 20, raising=False)
    monkeypatch.setattr(owned_process.os, 'getpgrp', lambda: 20, raising=False)
    kill = Mock()
    monkeypatch.setattr(owned_process.os, 'killpg', kill, raising=False)
    job = owned_process.ProcessJob()
    with pytest.raises(RuntimeError, match='own process session'):
        job.attach_and_resume(Mock(pid=30))
    job.close()
    kill.assert_not_called()


def test_posix_job_releases_worker_group_once(monkeypatch):
    monkeypatch.setattr(owned_process.os, 'name', 'posix')
    monkeypatch.setattr(owned_process.os, 'getpgid', lambda pid: pid, raising=False)
    monkeypatch.setattr(owned_process.os, 'getpgrp', lambda: 20, raising=False)
    kill = Mock()
    monkeypatch.setattr(owned_process.os, 'killpg', kill, raising=False)
    job = owned_process.ProcessJob()
    job.attach_and_resume(Mock(pid=30))
    job.close()
    job.close()
    kill.assert_called_once_with(30, getattr(owned_process.signal, 'SIGKILL', 9))


def test_mac_browser_uses_open_command_with_arguments(monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'darwin')
    monkeypatch.setattr(Path, 'is_dir', lambda path: str(path).replace('\\', '/').endswith('/Applications/Google Chrome.app'))
    launch = Mock()
    monkeypatch.setattr(assistant_commands.subprocess, 'Popen', launch)
    assert assistant_commands.run_command('open chrome', True) == 'Opening Google Chrome.'
    assert launch.call_args.args[0][0:2] == ['/usr/bin/open', '-a']
    assert launch.call_args.kwargs['shell'] is False


def test_mac_screen_mask_uses_retina_logical_coordinates(monkeypatch):
    from types import SimpleNamespace
    from PIL import Image
    import macos_support
    quartz = SimpleNamespace(CGMainDisplayID=lambda: 1, CGDisplayBounds=lambda _: SimpleNamespace(
        origin=SimpleNamespace(x=0, y=0), size=SimpleNamespace(width=100, height=80)))
    monkeypatch.setitem(sys.modules, 'Quartz', quartz)
    image = macos_support.mask_companion(Image.new('RGB', (200, 160), 'white'),
                                        {'x': 10, 'y': 10, 'width': 20, 'height': 30})
    assert image.size == (100, 80)
    assert image.getpixel((15, 15)) == (24, 24, 24)
    assert image.getpixel((60, 60)) == (255, 255, 255)


def test_mac_hotkey_permission_required_for_click_through(monkeypatch):
    from types import SimpleNamespace
    import macos_support
    monkeypatch.setitem(sys.modules, 'Quartz', SimpleNamespace(AXIsProcessTrusted=lambda: False))
    assert macos_support.start_hotkey(lambda: pytest.fail('No permission')) is None
