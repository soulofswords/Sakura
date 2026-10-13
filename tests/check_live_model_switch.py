"""Manual live settings-API test against the project-local Qwen runtime."""
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from fastapi.testclient import TestClient
import app
from llm import LLM
from ollama_runtime import stop

if __name__ == '__main__':
    original_settings = app.SETTINGS_FILE
    original_llm, original_tts = app.llm, app.tts
    try:
        with tempfile.TemporaryDirectory() as folder:
            app.SETTINGS_FILE = Path(folder) / 'settings.json'
            settings = json.loads(original_settings.read_text(encoding='utf-8-sig'))
            app.SETTINGS_FILE.write_text(json.dumps(settings), encoding='utf-8')
            app.llm = LLM(Path(folder) / 'memory.json')
            app.tts = None
            app.llm.configure_local(settings['ollama_model'], settings['ollama_models_folder'], context=2048)
            client = TestClient(app.app)
            for model in ['qwen3-vl:2b-instruct', 'qwen3-vl:4b-instruct', 'qwen3-vl:2b-instruct']:
                response = client.post('/api/settings', json={'llm_provider': 'ollama', 'ollama_model': model})
                assert response.status_code == 200, response.text
                assert app.llm.model == model and app.llm.vision_model == model
                loaded = requests.get(app.llm.base_url + '/api/ps', timeout=5).json()['models']
                assert not any(item['name'] != model for item in loaded), loaded
                result = requests.post(app.llm.base_url + '/api/chat', json={
                    'model': app.llm.model, 'messages': [{'role': 'user', 'content': 'Say hello in three words.'}],
                    'stream': False, 'think': False, 'keep_alive': '5m',
                    'options': {'num_ctx': 2048, 'num_predict': 20}}, timeout=180)
                result.raise_for_status()
                data = result.json()
                assert data['model'] == model and data['message']['content'].strip(), data
                loaded = requests.get(app.llm.base_url + '/api/ps', timeout=5).json()['models']
                assert len(loaded) == 1 and loaded[0]['name'] == model, loaded
                print('PASS', model, '| reply:', data['message']['content'].strip(),
                      '| loaded:', loaded[0]['name'], '| seconds:', round(data['total_duration'] / 1e9, 2), flush=True)
    finally:
        app.SETTINGS_FILE = original_settings
        app.llm, app.tts = original_llm, original_tts
        stop()
