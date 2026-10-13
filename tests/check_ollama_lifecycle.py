"""Manual integration check: real private server, warmup, close, and crash cleanup."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
import ollama_runtime

def gone(url):
    for _ in range(50):
        try:
            requests.get(url + '/api/tags', timeout=0.2)
        except requests.ConnectionError:
            return True
        time.sleep(0.1)
    return False

if __name__ == '__main__':
    url = ollama_runtime.server_for_folder('llm-models')
    response = requests.post(url + '/api/generate', json={
        'model': 'llama3.1:8b', 'stream': False, 'keep_alive': '15m',
        'options': {'num_ctx': 4096}}, timeout=90)
    response.raise_for_status()
    assert requests.get(url + '/api/ps').json()['models'], 'Model did not load'
    print('PASS: private instance starts and loads model', flush=True)
    ollama_runtime.stop()
    assert gone(url), 'Private server survived shutdown'
    print('PASS: explicit close stops private server and its job', flush=True)
    with tempfile.TemporaryDirectory() as folder:
        marker = Path(folder) / 'ready.json'
        source = ('import ollama_runtime,time,json; from pathlib import Path; '
                  'url=ollama_runtime.server_for_folder("llm-models"); '
                  f'Path({str(marker)!r}).write_text(json.dumps(url)); time.sleep(120)')
        child = subprocess.Popen([sys.executable, '-c', source], cwd=ollama_runtime.BASE_DIR)
        try:
            for _ in range(300):
                if marker.exists():
                    break
                if child.poll() is not None:
                    raise AssertionError('Owner failed to launch')
                time.sleep(0.1)
            url = json.loads(marker.read_text())
            child.kill()
            child.wait(timeout=10)
            assert gone(url), 'Private instance survived owner crash'
            print('PASS: owner crash also stops private instance', flush=True)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
