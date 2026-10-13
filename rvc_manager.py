"""Start Sakura's installed local RVC worker when a character voice is used."""
from pathlib import Path
import subprocess
import threading
import time
import requests
import atexit
import os
import sys
from owned_process import ProcessJob

BASE = Path(__file__).resolve().parent
_lock = threading.Lock()
_worker = None
_job = None

def _runtime_usable(root):
    """Whether this runtime can really import its packages on THIS machine.

    The CUDA runtime borrows its torch install from another application
    via a .pth redirect (an absolute path to that install's site-packages).
    On a different computer that target is gone and every import fails, so
    a redirected runtime only counts when all of its targets still exist.
    A runtime with a local torch package is always usable.
    """
    site = root / 'Lib' / 'site-packages'
    if sys.platform != 'win32':
        sites = list((root / 'lib').glob('python*/site-packages'))
        site = sites[0] if sites else site
    if not site.is_dir():
        return True  # unknown layout: don't reject, let the service decide
    if (site / 'torch').is_dir():
        return True
    redirects = list(site.glob('*.pth'))
    if not redirects:
        return False
    has_torch = False
    for pth in redirects:
        try:
            lines = pth.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError:
            return False
        for line in lines:
            target = line.strip()
            if not target or target.startswith('#') or target.startswith(('import ', 'import\t')):
                continue  # comment or executable line ('import x' / 'import\tx')
            # .pth paths may be relative to the site-packages folder itself.
            candidate = Path(target)
            if not candidate.is_absolute():
                candidate = site / candidate
            if not candidate.exists():
                return False
            has_torch = has_torch or (candidate / 'torch').is_dir()
    # An unrelated .pth file (e.g. setuptools' import hook) is not torch.
    return has_torch


def _runtime_python():
    """The RVC interpreter for this machine's GPU, preferring the vendor-
    matched runtime: CUDA torch for NVIDIA, torch-directml for AMD/Intel
    (created by setup-rvc-amd.ps1). Runtimes whose borrowed packages are
    missing on this machine are skipped; rvc_service.py itself adapts the
    device inside whichever runs."""
    from gpu_info import detect_gpu
    vendor = detect_gpu().get('vendor', 'cpu')
    if sys.platform == 'darwin':
        python = BASE / 'rvc-mac-runtime' / 'bin' / 'python'
        if python.is_file() and _runtime_usable(BASE / 'rvc-mac-runtime'):
            return python
        raise RuntimeError('Mac RVC is not installed. Use a built-in voice or run setup-rvc-macos.command.')
    order = {
        'nvidia': ('rvc-gpu-runtime', 'rvc-amd-runtime', 'rvc-runtime'),
        'amd': ('rvc-amd-runtime', 'rvc-gpu-runtime', 'rvc-runtime'),
        'intel': ('rvc-amd-runtime', 'rvc-gpu-runtime', 'rvc-runtime'),
    }.get(vendor, ('rvc-runtime', 'rvc-amd-runtime', 'rvc-gpu-runtime'))
    for name in order:
        python = BASE / name / 'Scripts' / 'python.exe'
        if python.is_file() and _runtime_usable(BASE / name):
            return python
    raise RuntimeError('No usable RVC runtime found. Install a self-contained RVC runtime; '
                       'for AMD/Intel, run setup-rvc-amd.ps1 in the Sakura folder.')


def ensure_rvc_service(timeout=90):
    global _worker, _job
    with _lock:
        def ready():
            try:
                response = requests.get('http://127.0.0.1:18888/health', timeout=1)
                payload = response.json()
                return response.status_code == 200 and isinstance(payload, dict) and payload.get('application') == 'sakura-rvc'
            except (requests.RequestException, ValueError):
                return False
        if ready():
            return
        python = _runtime_python()
        if not python.is_file():
            raise RuntimeError('The RVC runtime is not installed.')
        if _worker is None or _worker.poll() is not None:
            if _job is not None:
                _job.close()
                _job = None
            _job = ProcessJob()
            logs_dir = BASE / 'logs'
            logs_dir.mkdir(parents=True, exist_ok=True)
            log = open(logs_dir / 'rvc-service.log', 'a', encoding='utf-8')
            try:
                _worker = subprocess.Popen([str(python), '-u', str(BASE / 'rvc_service.py')],
                    cwd=str(BASE), stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=os.name != 'nt',
                    creationflags=(subprocess.CREATE_NO_WINDOW | 0x00000004) if os.name == 'nt' else 0)
                _job.attach_and_resume(_worker)
            except Exception:
                try:
                    if _worker is not None and _worker.poll() is None:
                        _worker.kill()
                        _worker.wait(timeout=5)
                finally:
                    _worker = None
                    _job.close()
                    _job = None
                raise
            finally:
                log.close()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if ready():
                return
            if _worker.poll() is not None:
                raise RuntimeError('RVC could not start. See logs/rvc-service.log for details.')
            time.sleep(0.5)
        raise RuntimeError('RVC is still starting. Try again shortly.')


def stop_rvc_service():
    """Release only the RVC worker owned by this Sakura process."""
    global _worker, _job
    with _lock:
        if _job is not None:
            _job.close()
            _job = None
        if _worker is not None and _worker.poll() is None:
            _worker.terminate()
            try:
                _worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _worker.kill()
                _worker.wait(timeout=5)
        _worker = None

atexit.register(stop_rvc_service)
