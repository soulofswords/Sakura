import io
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from PIL import Image
from urllib.parse import quote
from app import app

report_path = Path('models/model-audit.json')
report = json.loads(report_path.read_text(encoding='utf-8'))
client = TestClient(app)
for entry in report:
    entry['missing'] = []
    entry['invalidTextures'] = []
    for texture in entry.get('texturePaths', []):
        response = client.get('/models/' + quote(texture, safe='/'))
        if response.status_code != 200:
            entry['missing'].append(texture)
            continue
        try:
            with Image.open(io.BytesIO(response.content)) as image:
                image.load()
        except Exception as error:
            entry['invalidTextures'].append({'path':texture,'error':str(error)})
    print(json.dumps({'file':entry['file'],'missing':entry['missing'],'invalidTextures':entry['invalidTextures']},ensure_ascii=False))
report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
