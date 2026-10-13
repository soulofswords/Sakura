"""Generate a voice sample and verify copied RVC models without changing settings."""
import io
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
import soundfile as sf
from rvc_manager import ensure_rvc_service, stop_rvc_service

root = Path(__file__).resolve().parents[1]
results = []
try:
    response = requests.post('http://127.0.0.1:8766/api/tts/test',
        json={'voice':'emma_energetic','text':'Sakura is ready.'}, timeout=40)
    response.raise_for_status()
    audio = requests.get('http://127.0.0.1:8766' + response.json()['audio'], timeout=10).content
    assert len(audio) > 100
    results.append({'type':'built-in','ok':True,'bytes':len(audio)})
    print(json.dumps(results[-1]), flush=True)
    ensure_rvc_service(timeout=90)
    for model in (root / 'voices').glob('*/*.pth'):
        response = requests.post('http://127.0.0.1:18888/voice',
            files={'audio':('sample.mp3',audio,'audio/mpeg')},
            data={'model':model.name,'index_rate':.75},timeout=90)
        response.raise_for_status()
        samples, rate = sf.read(io.BytesIO(response.content))
        assert len(samples) > rate * .1
        results.append({'type':'rvc','model':model.relative_to(root).as_posix(),
            'ok':True,'seconds':len(samples)/rate,'sampleRate':rate})
        print(json.dumps(results[-1]), flush=True)
finally:
    stop_rvc_service()
    (root / 'audit-results/relocation/voices.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
