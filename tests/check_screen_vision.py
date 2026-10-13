"""Manual integration check against the running Sakura backend, without changing memory."""
import base64
import io
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, ImageGrab
import requests

def jpeg(image):
    image = image.convert('RGB')
    image.thumbnail((1600, 1200))
    output = io.BytesIO()
    image.save(output, format='JPEG', quality=82)
    return base64.b64encode(output.getvalue()).decode('ascii')

def check(image, initial, label):
    started = time.monotonic()
    response = requests.post('http://127.0.0.1:8766/api/chat', json={
        'text':'Screen integration check', 'screen_image':jpeg(image),
        'screen_reaction':True, 'screen_check':initial, 'defer_audio':True,
    }, timeout=90)
    response.raise_for_status()
    reply = response.json().get('reply', '').strip()
    assert reply, 'Empty visible response'
    assert not reply.startswith('Oops,'), reply
    assert '<think>' not in reply, 'Thinking leaked into visible reply'
    print(f'PASS: {label}: {time.monotonic()-started:.2f}s, {len(reply)} visible characters', flush=True)
    return reply

if __name__ == '__main__':
    status = requests.get('http://127.0.0.1:8766/api/screen/status', timeout=10).json()
    assert status.get('ready'), status
    assert status.get('model') == 'qwen3-vl:2b-instruct', status
    image = Image.new('RGB', (800,400), 'white')
    ImageDraw.Draw(image).text((40,150), 'SCREEN TEST: BLUE CAT 42', fill='black', font_size=52)
    result = check(image, True, 'screen toggle with test image')
    assert 'blue' in result.lower() or '42' in result, 'Test image content not recognized'
    for attempt in range(3):
        # Test the actual desktop image; avoid printing or saving its contents.
        check(ImageGrab.grab(), True, f'desktop capture {attempt+1}')
    check(ImageGrab.grab(), False, 'companion reaction')
