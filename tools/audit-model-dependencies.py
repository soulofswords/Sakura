"""Check asset references without opening models or altering user artwork."""
import json
import struct
import sys
from pathlib import Path
from fastapi.testclient import TestClient

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from app import app
source = root / 'audit-results/pmx-shading-library.json'
report = json.loads(source.read_text(encoding='utf-8'))
client = TestClient(app)
cache = {}
for item in report['models']:
    if item['status'] != 'parsed':
        continue
    folder = Path(item['file']).parent
    mapping_file = root / folder / 'textures.json'
    try:
        mapping = json.loads(mapping_file.read_text(encoding='utf-8')).get('textures', {}) if mapping_file.exists() else {}
    except (ValueError, OSError):
        mapping = {}
        item['mapping_error'] = 'Unreadable textures.json'
    mapping = {k.replace('\\', '/'): v for k, v in mapping.items()}
    missing = {'diffuse': [], 'sphere': []}
    for kind, indices in [('diffuse', item['diffuseIndices']), ('sphere', item['sphereIndices'])]:
        for index in indices:
            if index >= len(item['textures']):
                missing[kind].append(f'Invalid texture index {index}')
                continue
            name = item['textures'][index].replace('\\', '/')
            name = mapping.get(name, name).replace('\\', '/')
            asset = folder.relative_to('models').as_posix() + '/' + name
            if asset not in cache:
                response = client.post('/api/models/texture-check', json={'paths': [asset]})
                cache[asset] = response.status_code == 200 and not response.json().get('missing')
            if not cache[asset]:
                missing[kind].append(name)
    item['missingDiffuse'] = missing['diffuse']
    item['missingOptionalSphere'] = missing['sphere']

report['vrm'] = []
for file in sorted((root / 'models').rglob('*.vrm')):
    item = {'file': file.relative_to(root).as_posix()}
    try:
        with file.open('rb') as stream:
            header = stream.read(20)
            magic, version, length, chunk_length, chunk_type = struct.unpack('<4sIIII', header)
            if magic != b'glTF' or version != 2 or chunk_type != 0x4E4F534A or length != file.stat().st_size:
                raise ValueError('Invalid GLB header or file size')
            if chunk_length > length - 20:
                raise ValueError('Truncated GLB JSON chunk')
            data = json.loads(stream.read(chunk_length))
        missing = []
        for entry in data.get('images', []) + data.get('buffers', []):
            uri = entry.get('uri', '')
            if uri and not uri.startswith('data:') and not (file.parent / uri).is_file():
                missing.append(uri)
        item.update(status='parsed', missingDependencies=missing, materials=len(data.get('materials', [])))
    except (OSError, ValueError, struct.error) as error:
        item.update(status='error', error=str(error))
    report['vrm'].append(item)
report['live2d'] = []
for file in sorted((root / 'models').rglob('*.model3.json')):
    try:
        data = json.loads(file.read_text(encoding='utf-8'))
        refs = data.get('FileReferences', {})
        names = refs.get('Textures', []) + [refs.get('Moc'), refs.get('Physics')]
        report['live2d'].append({'file': file.relative_to(root).as_posix(), 'missingDependencies': [n for n in names if n and not (file.parent / n).is_file()]})
    except (ValueError, OSError) as error:
        report['live2d'].append({'file': file.relative_to(root).as_posix(), 'error': str(error)})
target = root / 'audit-results/model-library-shading-and-assets.json'
target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'pmx': len(report['models']), 'vrm': len(report['vrm']), 'live2d': len(report['live2d']),
    'pmxWithMissingDiffuse': sum(bool(m.get('missingDiffuse')) for m in report['models']),
    'pmxWithMissingOptionalSphere': sum(bool(m.get('missingOptionalSphere')) for m in report['models']),
    'parseErrors': sum(m['status'] == 'error' for m in report['models'])}))
