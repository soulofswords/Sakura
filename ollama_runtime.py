"""Run a private Ollama instance for a user-selected model store."""
import atexit
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
import requests
import sys
from config import BASE_DIR, OLLAMA_BASE_URL
from owned_process import ProcessJob

_lock = threading.RLock()
_job = None
_worker = None
_folder = None
_url = None
_default_job = None
_default_worker = None
_default_attempted = False


def validate_folder(folder):
    if not isinstance(folder, str):
        raise ValueError('Enter a local Ollama model-folder path.')
    if not folder.strip():
        return ''
    selected = Path(folder.strip()).expanduser()
    path = (selected if selected.is_absolute() else BASE_DIR / selected).resolve()
    if not path.is_dir() or not (path / 'blobs').is_dir() or not (path / 'manifests').is_dir():
        raise ValueError('Choose the Ollama models folder containing both blobs and manifests.')
    return str(path)


def build_ollama_env(base_env, vendor='cpu', vulkan_runner_present=False):
    """Environment for launching the bundled Ollama on this machine's GPU.

    The bundled runtime ships CUDA runners (NVIDIA) plus an experimental
    Vulkan runner that accelerates AMD Radeon and Intel Arc GPUs. Without
    a vendor flag an AMD machine would silently fall back to CPU, so
    Vulkan is enabled for every non-NVIDIA vendor when the runner exists.
    """
    environment = base_env.copy()
    if vendor not in ('nvidia', 'apple') and vulkan_runner_present:
        environment['OLLAMA_VULKAN'] = '1'
    return environment


def gpu_env():
    """build_ollama_env driven by live hardware detection."""
    from gpu_info import detect_gpu
    vulkan = (BASE_DIR / 'ollama-runtime' / 'lib' / 'ollama' / 'vulkan').is_dir()
    return build_ollama_env(os.environ, detect_gpu().get('vendor', 'cpu'), vulkan)


def _bundled_executable():
    if sys.platform != 'win32':
        bundled = BASE_DIR / 'ollama-runtime' / 'bin' / 'ollama'
        if bundled.is_file() and os.access(bundled, os.X_OK):
            return str(bundled)
        found = shutil.which('ollama')
        if found:
            return found
        if sys.platform == 'darwin':
            for candidate in (Path('/Applications/Ollama.app/Contents/Resources/ollama'),
                              Path('/opt/homebrew/bin/ollama'), Path('/usr/local/bin/ollama')):
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    return str(candidate)
        return None
    bundled = BASE_DIR / 'ollama-runtime' / 'ollama.exe'
    if bundled.is_file():
        return str(bundled)
    found = shutil.which('ollama')
    if found:
        return found
    candidate = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Ollama' / 'ollama.exe'
    return str(candidate) if candidate.is_file() else None


def default_models_store():
    """The store the bundled default server should serve: Sakura's local
    llm-models folder when it is a real Ollama store, else the machine
    default OLLAMA_MODELS location."""
    local = BASE_DIR / 'llm-models'
    if (local / 'blobs').is_dir() and (local / 'manifests').is_dir():
        return str(local)
    return str(Path(os.environ.get('OLLAMA_MODELS',
        str(Path.home() / '.ollama' / 'models'))).expanduser().resolve())


def _spawn_serve(executable, environment, log_path):
    """Start `ollama serve`; returns (job, worker) with output logged.

    The job owns a suspended Windows process until attach_and_resume; any
    failure between process creation and attach must not leak that
    half-started process or the job handle.
    """
    job = ProcessJob()
    worker = None
    try:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, 'ab') as log:
            worker = subprocess.Popen([executable, 'serve'], env=environment,
                stdout=log, stderr=subprocess.STDOUT,
                start_new_session=os.name != 'nt',
                creationflags=(subprocess.CREATE_NO_WINDOW | 0x00000004) if os.name == 'nt' else 0)
        job.attach_and_resume(worker)
    except Exception:
        if worker is not None:
            try:
                worker.terminate()
                worker.wait(timeout=5)
            except Exception:
                pass
        job.close()
        raise
    return job, worker


def _ollama_alive(url, timeout=1.0):
    """True only when a real Ollama answers: HTTP 200 plus the model-list
    JSON shape. Anything else (another app, a catch-all page, a dead port)
    counts as 'not running' so the bundled server can take the port."""
    try:
        response = requests.get(url + '/api/tags', timeout=timeout)
        if response.status_code != 200:
            return False
        payload = response.json()
        return isinstance(payload, dict) and isinstance(payload.get('models'), list)
    except (requests.RequestException, ValueError):
        return False


def _wait_ready(worker, url, deadline):
    while time.monotonic() < deadline:
        if worker.poll() is not None:
            return False
        if _ollama_alive(url, timeout=0.5):
            return True
        time.sleep(0.1)
    return False


def ensure_default_server(timeout=25):
    """Start the bundled Ollama on the default port if nothing serves it.

    A fresh computer has no Ollama service, so the app starts its own
    bundled server against Sakura's local model store — with the Vulkan
    runner on AMD and Intel GPUs. Attempts once per process (a later
    release_default_server allows a retry) and never raises: a machine
    without a usable runtime stays 'offline', which the UI handles.
    """
    global _default_attempted
    with _lock:
        if _default_attempted:
            return False
        _default_attempted = True
    if _ollama_alive(OLLAMA_BASE_URL):
        return True  # a system Ollama or an earlier start is already up
    executable = _bundled_executable()
    if not executable:
        return False
    try:
        environment = gpu_env()
        # Pin the child to the probed address: an inherited OLLAMA_HOST
        # (e.g. left over on a private port) would make it listen where we
        # never check.
        environment.update(OLLAMA_HOST=OLLAMA_BASE_URL.split('//', 1)[-1],
                           OLLAMA_MODELS=default_models_store(),
                           OLLAMA_NUM_PARALLEL='1', OLLAMA_MAX_LOADED_MODELS='1')
        job, worker = _spawn_serve(executable, environment, BASE_DIR / 'logs' / 'ollama-local.log')
        globals()['_default_job'], globals()['_default_worker'] = job, worker
        if not _wait_ready(worker, OLLAMA_BASE_URL, time.monotonic() + timeout):
            _stop_default()
            return False
        return True
    except Exception:
        _stop_default()
        return False


def _stop_default():
    job = globals().get('_default_job')
    worker = globals().get('_default_worker')
    if job is not None:
        job.close()
        globals()['_default_job'] = None
    if worker is not None and worker.poll() is None:
        worker.terminate()
        try:
            worker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait(timeout=5)
    globals()['_default_worker'] = None


def release_default_server():
    """Stop the auto-started default server and permit a later restart."""
    global _default_attempted
    _stop_default()
    _default_attempted = False


def _stop_private():
    """Terminate only the user-selected-folder server owned by this process."""
    global _job, _worker, _folder, _url
    if _job is not None:
        _job.close()  # Terminates the server AND all its model runners.
        globals()['_job'] = None
    if _worker is not None and _worker.poll() is None:
        _worker.terminate()
        try:
            _worker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _worker.kill()
            _worker.wait(timeout=5)
    globals()['_worker'] = globals()['_folder'] = globals()['_url'] = None


def stop():
    """Full shutdown: private servers and the auto-started default."""
    _stop_private()
    _stop_default()

atexit.register(stop)

def server_for_folder(folder):
    global _worker, _folder, _url, _job
    folder = validate_folder(folder)
    if not folder:
        return OLLAMA_BASE_URL
    default_store = Path(os.environ.get('OLLAMA_MODELS', str(Path.home() / '.ollama' / 'models'))).expanduser().resolve()
    if Path(folder) == default_store:
        return OLLAMA_BASE_URL
    with _lock:
        if _worker is not None and _worker.poll() is None and folder == _folder:
            return _url
        executable = _bundled_executable()
        if not executable:
            raise ValueError('Install Ollama before using a local model folder.')
        port = None
        for candidate_port in range(11435, 11446):
            with socket.socket() as probe:
                try:
                    probe.bind(('127.0.0.1', candidate_port))
                    port = candidate_port
                    break
                except OSError:
                    continue
        if port is None:
            raise ValueError('No free port for the selected Ollama model folder.')
        # Only the private server is replaced here. The auto-started default
        # server keeps running on its own port, so switching folders and
        # back never leaves the app without a default instance.
        _stop_private()
        environment = gpu_env()
        environment.update(OLLAMA_MODELS=folder, OLLAMA_HOST=f'127.0.0.1:{port}',
                           OLLAMA_NUM_PARALLEL='1', OLLAMA_MAX_LOADED_MODELS='1')
        try:
            _job, _worker = _spawn_serve(executable, environment, BASE_DIR / 'logs' / 'ollama-local.log')
        except Exception:
            _stop_private()
            raise
        _folder, _url = folder, f'http://127.0.0.1:{port}'
        if not _wait_ready(_worker, _url, time.monotonic() + 20):
            _stop_private()
            raise ValueError('Ollama did not become ready. Check logs/ollama-local.log.')
        return _url

def list_models(folder=''):
    url = server_for_folder(folder)
    try:
        response = requests.get(url + '/api/tags', timeout=3)
        response.raise_for_status()
        return [{'name': m['name'], 'size': m.get('size', 0)} for m in response.json().get('models', [])]
    except (requests.RequestException, ValueError, KeyError) as exc:
        raise ValueError('Could not read local models. Start Ollama or check the selected folder.') from exc
