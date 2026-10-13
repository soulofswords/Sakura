"""Manual integration check for the bundled runtime and installed Qwen 2B."""
import base64
import io
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from PIL import Image
from ollama_runtime import server_for_folder, stop

if __name__ == '__main__':
    try:
        url = server_for_folder('llm-models')
        tags = requests.get(url + '/api/tags', timeout=5).json()
        print('Installed:', ', '.join(item['name'] for item in tags['models']), flush=True)
        model = 'qwen3-vl:2b-instruct'
        for image in [False, True]:
            message = {'role': 'user', 'content': 'Reply with a short hello.'}
            if image:
                buffer = io.BytesIO()
                Image.new('RGB', (224, 224), 'red').save(buffer, format='JPEG')
                message = {'role': 'user', 'content': 'What color fills this image? Answer briefly.',
                           'images': [base64.b64encode(buffer.getvalue()).decode()]}
            response = requests.post(url + '/api/chat', json={
                'model': model, 'messages': [message], 'think': False,
                'stream': False, 'keep_alive': '5m',
                'options': {'num_ctx': 4096 if image else 2048, 'num_predict': 40}}, timeout=180)
            response.raise_for_status()
            data = response.json()
            reply = data['message']['content'].strip()
            if not reply:
                raise RuntimeError('Empty reply')
            print(('Vision' if image else 'Chat') + ': ' + reply, flush=True)
            print('Total seconds:', round(data.get('total_duration', 0) / 1e9, 2), flush=True)
    finally:
        stop()
