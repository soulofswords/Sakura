"""Audit source assets through the same resolver used by the running app."""
import asyncio
import json
import struct
import sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import serve_model_file, MODELS_DIR

OUTPUT = Path('audit-results/all-model-hair-2026-10-10')

async def main():
    source = json.loads(Path('audit-results/library-render-audit.json').read_text(encoding='utf-8'))
    cache = {}
    report = []
    for item in source:
        model = Path(item['file'])
        missing, invalid = [], []
        used = {m.get('texture') for m in item.get('materials', [])}
        used |= {m.get('sphere') for m in item.get('materials', []) if m.get('sphereMode')}
        for index, name in enumerate(item.get('textures', [])):
            if index not in used:
                continue
            # MMDLoader appends even an exporter's absolute Windows texture
            # reference to the model URL. Preserve that request so the app's
            # basename/remapping resolver can handle it, rather than treating
            # the exporter's drive letter as this machine's filesystem root.
            requested = model.parent.relative_to('models').as_posix() + '/' + name.replace('\\', '/')
            if requested not in cache:
                response = await serve_model_file(requested)
                if response.headers.get('X-Sakura-Asset-Fallback') == 'missing' or response.status_code != 200:
                    cache[requested] = {'missing': True}
                else:
                    try:
                        with Image.open(response.path) as image:
                            image.load()
                            cache[requested] = {'size': image.size, 'format': image.format}
                    except Exception as error:
                        cache[requested] = {'error': str(error)}
            outcome = cache[requested]
            if outcome.get('missing'):
                missing.append({'index': index, 'path': requested})
            elif outcome.get('error'):
                invalid.append({'index': index, 'path': requested, 'error': outcome['error']})
        report.append({'path': model.relative_to('models').as_posix(),
            'missing': missing, 'invalid': invalid, 'parseError': item.get('error'),
            'badVertices': item.get('badVertices', 0), 'badFaces': item.get('badFaces', 0)})
        if len(report) % 100 == 0:
            print(f'Assets checked: {len(report)}/{len(source)}', flush=True)
    vrms = []
    for file in MODELS_DIR.rglob('*.vrm'):
        try:
            data = file.read_bytes()
            magic, version, length = struct.unpack_from('<4sII', data)
            if magic != b'glTF' or version != 2 or length != len(data):
                raise ValueError('Invalid GLB header or truncated file')
            chunk_length, chunk_type = struct.unpack_from('<II', data, 12)
            doc = json.loads(data[20:20+chunk_length])
            vrms.append({'path': file.relative_to(MODELS_DIR).as_posix(), 'ok': True,
                'meshes': len(doc.get('meshes', [])), 'materials': len(doc.get('materials', [])),
                'extensions': doc.get('extensionsUsed', [])})
        except Exception as error:
            vrms.append({'path': file.relative_to(MODELS_DIR).as_posix(), 'ok': False, 'error': str(error)})
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / 'assets.json').write_text(json.dumps({'pmx': report, 'vrm': vrms},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pmx':len(report),'vrm':len(vrms),'missingTextureModels':sum(bool(x['missing']) for x in report),
        'invalidTextureModels':sum(bool(x['invalid']) for x in report),'output':str(OUTPUT/'assets.json')}),flush=True)

asyncio.run(main())
