"""AMD / multi-vendor GPU adaptation tests.

Sakura must run unchanged on NVIDIA, AMD, Intel and GPU-less machines:
- gpu_info classifies the GPU vendor from Windows queries,
- Ollama launches with the Vulkan runner on non-NVIDIA GPUs,
- torch services fall back cuda -> DirectML -> CPU safely.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gpu_info
import ollama_runtime
import rvc_manager


@pytest.fixture(autouse=True)
def _clean_gpu_cache(monkeypatch):
    """detect_gpu() caches per process. Clear before and after every test so
    a fake vendor from one test can never leak into another module's code
    (rvc_manager and the Ollama launcher both read it)."""
    # These vendor/runtime fixtures model Windows; Mac has its own test matrix.
    monkeypatch.setattr(sys, 'platform', 'win32')
    cached_detect = gpu_info.detect_gpu
    cached_detect.cache_clear()
    yield
    cached_detect.cache_clear()


def _set_gpus(monkeypatch, names):
    monkeypatch.setattr(gpu_info, '_video_controller_names', lambda: names)
    gpu_info.detect_gpu.cache_clear()


def test_classify_prefers_nvidia_over_amd(monkeypatch):
    # Dual-GPU laptop: CUDA is the backend every subsystem prefers.
    _set_gpus(monkeypatch, ['AMD Radeon(TM) Graphics', 'NVIDIA GeForce RTX 4060'])
    assert gpu_info.detect_gpu()['vendor'] == 'nvidia'


def test_classify_amd_radeon(monkeypatch):
    _set_gpus(monkeypatch, ['AMD Radeon RX 7800 XT'])
    assert gpu_info.detect_gpu()['vendor'] == 'amd'


def test_classify_intel_and_cpu(monkeypatch):
    _set_gpus(monkeypatch, ['Intel(R) Arc(TM) A770'])
    assert gpu_info.detect_gpu()['vendor'] == 'intel'
    _set_gpus(monkeypatch, [])
    assert gpu_info.detect_gpu()['vendor'] == 'cpu'


def test_build_ollama_env_vulkan_matrix():
    base = {'PATH': 'x'}
    # NVIDIA keeps CUDA discovery untouched.
    env = ollama_runtime.build_ollama_env(base, 'nvidia', vulkan_runner_present=True)
    assert 'OLLAMA_VULKAN' not in env
    # AMD/Intel/CPU get Vulkan when the runner ships.
    for vendor in ('amd', 'intel', 'cpu'):
        env = ollama_runtime.build_ollama_env(base, vendor, vulkan_runner_present=True)
        assert env['OLLAMA_VULKAN'] == '1'
    # No Vulkan runner in the bundle: flag stays unset everywhere.
    env = ollama_runtime.build_ollama_env(base, 'amd', vulkan_runner_present=False)
    assert 'OLLAMA_VULKAN' not in env


def test_build_ollama_env_does_not_mutate_input():
    base = {'PATH': 'x'}
    ollama_runtime.build_ollama_env(base, 'amd', vulkan_runner_present=True)
    assert 'OLLAMA_VULKAN' not in base


def test_pick_torch_device_order():
    sentinel = object()
    # CUDA wins even when DirectML exists.
    assert gpu_info.pick_torch_device(True, lambda: sentinel) == ('cuda:0', False)
    # DirectML used when CUDA is absent and the factory works.
    assert gpu_info.pick_torch_device(False, lambda: sentinel) == (sentinel, True)
    # A broken DirectML install falls back to CPU, never raises.
    def exploding():
        raise RuntimeError('driver mismatch')
    assert gpu_info.pick_torch_device(False, exploding) == ('cpu:0', False)
    assert gpu_info.pick_torch_device(False, None) == ('cpu:0', False)
    # A weird cuda_available object (not bool) must not explode either.
    class Weird:
        def __bool__(self):
            raise RuntimeError('no backend')
    assert gpu_info.pick_torch_device(Weird(), None) == ('cpu:0', False)


def test_ensure_default_server_attempts_once_and_never_raises(monkeypatch):
    monkeypatch.setattr(ollama_runtime, '_default_attempted', False)
    # No server responds and no executable exists: clean False, no raise.
    class DeadResponse:
        status_code = 503

    import requests as requests_module
    monkeypatch.setattr(ollama_runtime.requests, 'get', lambda *a, **k: DeadResponse())
    monkeypatch.setattr(ollama_runtime, '_bundled_executable', lambda: None)
    assert ollama_runtime.ensure_default_server() is False
    # Second call short-circuits even if an executable appears.
    monkeypatch.setattr(ollama_runtime, '_bundled_executable', lambda: 'ollama.exe')
    assert ollama_runtime.ensure_default_server() is False


def test_rvc_runtime_python_prefers_vendor_runtime(monkeypatch, tmp_path):
    def fake_detect():
        return {'vendor': 'amd', 'names': ['AMD Radeon RX 7800 XT']}
    monkeypatch.setattr(rvc_manager, 'BASE', tmp_path)
    (tmp_path / 'rvc-gpu-runtime' / 'Scripts').mkdir(parents=True)
    (tmp_path / 'rvc-gpu-runtime' / 'Scripts' / 'python.exe').write_bytes(b'')
    picked = rvc_manager._runtime_python()
    # Only the CUDA runtime exists: used as fallback even on AMD.
    assert picked == tmp_path / 'rvc-gpu-runtime' / 'Scripts' / 'python.exe'

    # Add the DirectML runtime: it wins on AMD.
    amd = tmp_path / 'rvc-amd-runtime' / 'Scripts'
    amd.mkdir(parents=True)
    (amd / 'python.exe').write_bytes(b'')
    import gpu_info as gi
    monkeypatch.setattr('gpu_info.detect_gpu', fake_detect)
    assert rvc_manager._runtime_python() == amd / 'python.exe'


def test_rvc_runtime_skips_borrowed_packages_missing(monkeypatch, tmp_path):
    # The CUDA runtime borrows torch from another app via a .pth redirect;
    # on a machine without that app the runtime must be skipped.
    def fake_detect():
        return {'vendor': 'nvidia', 'names': ['NVIDIA GeForce RTX 3080']}
    monkeypatch.setattr(rvc_manager, 'BASE', tmp_path)
    monkeypatch.setattr('gpu_info.detect_gpu', fake_detect)

    gpu_site = tmp_path / 'rvc-gpu-runtime' / 'Lib' / 'site-packages'
    gpu_site.mkdir(parents=True)
    (tmp_path / 'rvc-gpu-runtime' / 'Scripts').mkdir(parents=True)
    (tmp_path / 'rvc-gpu-runtime' / 'Scripts' / 'python.exe').write_bytes(b'')
    (gpu_site / 'comfy_gpu.pth').write_text(
        r'C:\Does\Not\Exist\ComfyUI\python_embeded\Lib\site-packages\n', encoding='ascii')

    amd = tmp_path / 'rvc-amd-runtime'
    amd_site = amd / 'Lib' / 'site-packages'
    amd_site.mkdir(parents=True)
    (amd / 'Scripts').mkdir(parents=True)
    (amd / 'Scripts' / 'python.exe').write_bytes(b'')
    (amd_site / 'torch').mkdir()

    picked = rvc_manager._runtime_python()
    # The redirected CUDA runtime is unusable here, so the self-contained
    # AMD runtime wins even though NVIDIA is the vendor.
    assert picked == amd / 'Scripts' / 'python.exe'


def test_rvc_runtime_accepts_local_torch(monkeypatch, tmp_path):
    def fake_detect():
        return {'vendor': 'nvidia', 'names': ['NVIDIA GeForce RTX 3080']}
    monkeypatch.setattr(rvc_manager, 'BASE', tmp_path)
    monkeypatch.setattr('gpu_info.detect_gpu', fake_detect)
    gpu = tmp_path / 'rvc-gpu-runtime'
    (gpu / 'Scripts').mkdir(parents=True)
    (gpu / 'Scripts' / 'python.exe').write_bytes(b'')
    (gpu / 'Lib' / 'site-packages' / 'torch').mkdir(parents=True)
    assert rvc_manager._runtime_python() == gpu / 'Scripts' / 'python.exe'


def test_rvc_service_imports_adaptively():
    # The service module itself lives in an isolated runtime; here we only
    # assert the shared helper it depends on exposes the right contract.
    assert callable(gpu_info.detect_gpu)
    assert callable(gpu_info.pick_torch_device)


def test_runtime_relative_redirect_and_import_tab(tmp_path):
    site = tmp_path / 'Lib' / 'site-packages'
    (site / 'borrowed' / 'torch').mkdir(parents=True)
    (site / 'paths.pth').write_text('import\tsys\nborrowed\n', encoding='utf-8')
    assert rvc_manager._runtime_usable(tmp_path)
    (site / 'paths.pth').write_text('import\tsys\nmissing\n', encoding='utf-8')
    assert not rvc_manager._runtime_usable(tmp_path)


def test_unrelated_pth_is_not_a_usable_torch_runtime(tmp_path):
    site = tmp_path / 'Lib' / 'site-packages'
    site.mkdir(parents=True)
    (site / 'hook.pth').write_text('import sys\n', encoding='utf-8')
    assert not rvc_manager._runtime_usable(tmp_path)


def test_all_broken_runtimes_give_actionable_error(monkeypatch, tmp_path):
    monkeypatch.setattr(rvc_manager, 'BASE', tmp_path)
    with pytest.raises(RuntimeError, match='No usable RVC runtime'):
        rvc_manager._runtime_python()


def test_failed_rvc_attach_cleans_process_and_job(monkeypatch, tmp_path):
    (tmp_path/'rvc_service.py').write_text('# worker fixture')
    from unittest.mock import Mock
    worker = Mock()
    worker.poll.return_value = None
    job = Mock()
    job.attach_and_resume.side_effect = RuntimeError('attach failed')
    monkeypatch.setattr(rvc_manager, 'BASE', tmp_path)
    monkeypatch.setattr(rvc_manager, '_worker', None)
    monkeypatch.setattr(rvc_manager, '_job', None)
    monkeypatch.setattr(rvc_manager, '_runtime_python', lambda: Path(sys.executable))
    monkeypatch.setattr(rvc_manager.requests, 'get', lambda *a, **k: (_ for _ in ()).throw(ValueError()))
    monkeypatch.setattr(rvc_manager, 'ProcessJob', lambda: job)
    monkeypatch.setattr(rvc_manager.subprocess, 'Popen', lambda *a, **k: worker)
    with pytest.raises(RuntimeError, match='attach failed'):
        rvc_manager.ensure_rvc_service()
    worker.kill.assert_called_once()
    worker.wait.assert_called_once_with(timeout=5)
    job.close.assert_called_once()
    assert rvc_manager._worker is None and rvc_manager._job is None


@pytest.mark.parametrize('payload,status,expected', [
    ({'models': []}, 200, True), ({'models': []}, 503, False),
    ({'other': []}, 200, False), ([], 200, False),
])
def test_ollama_identity_validation(monkeypatch, payload, status, expected):
    from unittest.mock import Mock
    response = Mock(status_code=status)
    response.json.return_value = payload
    monkeypatch.setattr(ollama_runtime.requests, 'get', lambda *a, **k: response)
    assert ollama_runtime._ollama_alive('http://127.0.0.1:11434') is expected


def test_ollama_failed_spawn_closes_job(monkeypatch, tmp_path):
    from unittest.mock import Mock
    job = Mock()
    monkeypatch.setattr(ollama_runtime, 'ProcessJob', lambda: job)
    def fail(*args, **kwargs):
        raise OSError('cannot spawn')
    monkeypatch.setattr(ollama_runtime.subprocess, 'Popen', fail)
    with pytest.raises(OSError, match='cannot spawn'):
        ollama_runtime._spawn_serve('missing.exe', {}, tmp_path / 'test.log')
    job.close.assert_called_once()


def test_default_server_pins_host_and_can_restart(monkeypatch, tmp_path):
    from unittest.mock import Mock
    monkeypatch.setattr(ollama_runtime, 'BASE_DIR', tmp_path)
    monkeypatch.setattr(ollama_runtime, '_default_attempted', False)
    monkeypatch.setattr(ollama_runtime, '_default_job', None)
    monkeypatch.setattr(ollama_runtime, '_default_worker', None)
    monkeypatch.setattr(ollama_runtime, '_ollama_alive', lambda *a, **k: False)
    monkeypatch.setattr(ollama_runtime, '_bundled_executable', lambda: 'ollama.exe')
    monkeypatch.setattr(ollama_runtime, 'gpu_env', lambda: {'OLLAMA_HOST': 'bad:9999'})
    monkeypatch.setattr(ollama_runtime, '_wait_ready', lambda *a: True)
    worker = Mock()
    worker.poll.return_value = 0
    job = Mock()
    spawn = Mock(return_value=(job, worker))
    monkeypatch.setattr(ollama_runtime, '_spawn_serve', spawn)
    assert ollama_runtime.ensure_default_server()
    assert spawn.call_args.args[1]['OLLAMA_HOST'] == ollama_runtime.OLLAMA_BASE_URL.split('//', 1)[-1]
    ollama_runtime.release_default_server()
    job.close.assert_called_once()
    assert ollama_runtime.ensure_default_server()
    assert spawn.call_count == 2
    ollama_runtime.release_default_server()
