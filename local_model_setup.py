"""Optional, verified local AI installation. No model is included in the app installer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import signal
import posixpath
import tarfile
import tempfile
import zipfile
import requests

BASE = Path(__file__).resolve().parent
MODEL_OPTIONS = [
    ('2b','qwen3-vl:2b-instruct','Qwen3-VL 2B',8,4,8,'~2 GB'),
    ('4b','qwen3-vl:4b-instruct','Qwen3-VL 4B',16,8,10,'~3.3 GB'),
    ('qwen38-27b','qwen3.8:27b','Qwen 3.8 27B',48,24,35,'~18 GB'),
    ('gemma3-4b','gemma3:4b','Gemma 3 4B',16,8,10,'~3.4 GB'),
    ('gemma3-12b','gemma3:12b','Gemma 3 12B',32,16,20,'~8.2 GB'),
    ('gemma3-27b','gemma3:27b','Gemma 3 27B',48,24,35,'~17 GB'),
    ('qwen35-4b','qwen3.5:4b','Qwen 3.5 4B',16,8,12,'~4 GB'),
    ('qwen35-9b','qwen3.5:9b','Qwen 3.5 9B',32,16,20,'~7.6 GB'),
]
MODELS = {row[0]:row[1] for row in MODEL_OPTIONS}
MODEL_DISK = {row[0]:row[5] for row in MODEL_OPTIONS}
RELEASE = 'https://github.com/ollama/ollama/releases/download/v0.40.2/'
RUNTIMES = {
    'win32': ('ollama-windows-amd64.zip', 'e29ad1d5063dd4b54b2492d9b00adab2cff9621bfa654b6c92aa8d6f1fdfe7fc'),
    'darwin': ('ollama-darwin.tgz', 'e888b7637291ceb80b622c00ea067f62c86d9c50d419b3eb903032e4f1f8a4f6'),
}

def progress(message, percent=None):
    print(json.dumps({'message': message, 'percent': percent}), flush=True)

def installed(base=BASE):
    """Check the private store without starting an AI process."""
    runtime = base / 'ollama-runtime' / ('ollama.exe' if sys.platform == 'win32' else 'bin/ollama')
    if not runtime.is_file():
        return False
    try:
        settings = base / 'settings.json'
        cfg = json.loads(settings.read_text(encoding='utf-8-sig')) if settings.exists() else {}
        name = cfg.get('ollama_model', MODELS['2b'])
        repo, tag = name.rsplit(':', 1)
        if name not in MODELS.values():
            return False
        store = Path(cfg.get('ollama_models_folder') or base / 'llm-models')
        if not store.is_absolute():
            store = base / store
        manifest = json.loads((store / 'manifests/registry.ollama.ai/library' / repo / tag).read_text())
        parts = [manifest['config'], *manifest['layers']]
        return all((store / 'blobs' / item['digest'].replace(':', '-')).is_file()
                   and (store / 'blobs' / item['digest'].replace(':', '-')).stat().st_size == item['size']
                   for item in parts)
    except (OSError, ValueError, KeyError, TypeError):
        return False

def extract(archive, target):
    """Reject traversal, symlinks and special files before extracting anything."""
    target = Path(target).resolve()
    def safe(name):
        normalized = name.replace('\\', '/')
        if ':' in normalized or normalized.startswith('/') or '..' in normalized.split('/'):
            raise ValueError('Unsafe runtime archive path')
        return normalized
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as reader:
            for item in reader.infolist():
                safe(item.filename)
                if (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('Runtime archive contains a symlink')
            reader.extractall(target)
    else:
        with tarfile.open(archive) as reader:
            entries = reader.getmembers()
            for item in entries:
                safe(item.name)
                if item.issym() or item.islnk():
                    destination = posixpath.normpath(posixpath.join(posixpath.dirname(item.name), item.linkname) if item.issym() else item.linkname)
                    safe(destination)
                elif not (item.isfile() or item.isdir()):
                    raise ValueError('Runtime archive contains a special file')
            reader.extractall(target, members=entries, filter='data')

def ensure_runtime(base=BASE):
    executable = base / 'ollama-runtime' / ('ollama.exe' if sys.platform == 'win32' else 'bin/ollama')
    if executable.is_file():
        return
    if sys.platform not in RUNTIMES:
        raise RuntimeError('Local download supports Windows x64 and Apple Silicon macOS.')
    name, expected = RUNTIMES[sys.platform]
    cache = base / 'downloads'
    cache.mkdir(exist_ok=True)
    archive = cache / name
    progress('Downloading optional local AI runtime…', 0)
    digest = hashlib.sha256()
    with requests.get(RELEASE + name, stream=True, timeout=(30, 120)) as response:
        response.raise_for_status()
        total = int(response.headers.get('Content-Length', 0))
        done = 0
        with archive.open('wb') as output:
            for chunk in response.iter_content(1024 * 1024):
                output.write(chunk); digest.update(chunk); done += len(chunk)
                progress('Downloading local AI runtime', int(done * 100 / total) if total else None)
    if digest.hexdigest() != expected:
        archive.unlink(missing_ok=True)
        raise RuntimeError('Runtime checksum mismatch. Please retry the download.')
    progress('Installing verified local AI runtime…')
    with tempfile.TemporaryDirectory(dir=base, prefix='runtime-setup-') as temporary:
        staging = Path(temporary)
        # Ollama's official macOS tarball is flat: keep its sibling libraries
        # next to the executable under bin/, where our runtime manager looks.
        extract(archive, staging / 'bin' if sys.platform == 'darwin' else staging)
        expected_exe = staging / ('ollama.exe' if sys.platform == 'win32' else 'bin/ollama')
        if not expected_exe.is_file():
            raise RuntimeError('Runtime archive is missing its executable.')
        if sys.platform == 'darwin':
            expected_exe.chmod(0o755)
        shutil.move(str(staging), str(base / 'ollama-runtime'))
    archive.unlink(missing_ok=True)

def install(choice, base=BASE):
    if choice not in MODELS:
        raise ValueError('Choose a supported vision model from the selector.')
    if shutil.disk_usage(base).free < MODEL_DISK[choice] * 1024**3:
        raise RuntimeError(f'Please free at least {MODEL_DISK[choice]} GB before installing this model and runtime.')
    ensure_runtime(base)
    store = base / 'llm-models'
    for folder in ('blobs', 'manifests'):
        (store / folder).mkdir(parents=True, exist_ok=True)
    import ollama_runtime
    try:
        url = ollama_runtime.server_for_folder(str(store))
        progress('Downloading ' + MODELS[choice] + ' (cancelled model downloads can resume)…', 0)
        with requests.post(url + '/api/pull', json={'model': MODELS[choice], 'stream': True},
                           stream=True, timeout=(30, 180)) as response:
            response.raise_for_status()
            success = False
            for line in response.iter_lines():
                if not line:
                    continue
                item = json.loads(line)
                if item.get('error'):
                    raise RuntimeError(item['error'])
                total = item.get('total', 0)
                progress(item.get('status', 'Downloading model'),
                         int(item.get('completed', 0) * 100 / total) if total else None)
                success = success or item.get('status') == 'success'
            if not success:
                raise RuntimeError('Model download ended before completion. Retry to resume.')
        check = requests.post(url + '/api/show', json={'model': MODELS[choice]}, timeout=30)
        check.raise_for_status()
        if 'vision' not in check.json().get('capabilities', []):
            raise RuntimeError('This runtime did not confirm vision support for the downloaded model. Update Ollama and retry. Your previous model settings were preserved.')
        settings = base / 'settings.json'
        cfg = json.loads(settings.read_text(encoding='utf-8-sig')) if settings.exists() else {}
        cfg.update(llm_provider='ollama', ollama_model=MODELS[choice],
                   ollama_vision_model=MODELS[choice], ollama_models_folder=str(store),
                   ollama_context=2048 if choice == '2b' else 4096)
        temporary = settings.with_suffix('.setup.tmp')
        temporary.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
        temporary.replace(settings)
        progress('Local AI is ready.', 100)
    finally:
        ollama_runtime.stop()

if __name__ == '__main__':
    # Cancellation must unwind finally blocks and stop the private runtime on macOS.
    if sys.platform != 'win32':
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(130))
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--install', choices=MODELS)
    args = parser.parse_args()
    if args.check:
        sys.exit(0 if installed() else 2)
    try:
        if not args.install:
            parser.error('Use --check or --install with a model selector ID')
        install(args.install)
    except Exception as error:
        progress(str(error))
        sys.exit(1)
