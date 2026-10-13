"""Install Sakura's vision model into its selected local store without opening the GUI."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from config import BASE_DIR, OLLAMA_VISION_MODEL
from ollama_runtime import server_for_folder, stop

if __name__ == '__main__':
    settings = json.loads((BASE_DIR / 'settings.json').read_text(encoding='utf-8'))
    try:
        url = server_for_folder(settings.get('ollama_models_folder') or 'llm-models')
        model = sys.argv[1] if len(sys.argv) > 1 else OLLAMA_VISION_MODEL
        response = requests.post(url + '/api/pull', json={'model':model,'stream':True},
                                 stream=True, timeout=(5,300))
        response.raise_for_status()
        last_progress = -10
        last_status = ''
        for line in response.iter_lines():
            if not line:
                continue
            result = json.loads(line)
            if result.get('error'):
                raise RuntimeError(result['error'])
            status = result.get('status','')
            total = result.get('total',0)
            progress = int(result.get('completed',0)*100/total) if total else 0
            if status != last_status or progress >= last_progress + 5:
                print(status, f'{progress}%' if total else '', flush=True)
                last_progress, last_status = progress, status
        print('Vision model installed and verified.', flush=True)
    finally:
        stop()
