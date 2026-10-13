"""Check screen-reaction and voice APIs with a known, non-private test image."""
import base64
from pathlib import Path
import time
import requests

if __name__ == '__main__':
    url = 'http://127.0.0.1:8766'
    sample = Path(__file__).with_name('screen-vision-sample.jpg')
    image = base64.b64encode(sample.read_bytes()).decode()
    for initial in [True, False]:
        start = time.monotonic()
        response = requests.post(url + '/api/chat', json={'text': 'Screen companion reaction',
            'screen_image': image, 'screen_reaction': True, 'screen_check': initial, 'defer_audio': True}, timeout=120)
        response.raise_for_status()
        reply = response.json()['reply']
        print(('Initial' if initial else 'Automatic') + ': ' + reply, flush=True)
        print('Seconds:', round(time.monotonic() - start, 2), flush=True)
        if initial:
            speech = requests.post(url + '/api/tts/speak', json={'text': reply}, timeout=90)
            if not speech.ok:
                print('Voice error:', speech.text, flush=True)
                continue
            audio = requests.get(url + speech.json()['audio'], timeout=10)
            audio.raise_for_status()
            print('Voice audio bytes:', len(audio.content), flush=True)
