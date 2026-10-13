"""Check the copied project inventory and hash essential model/runtime files."""
import hashlib
import json
from pathlib import Path
import sys

source = Path(sys.argv[1])
target = Path(__file__).resolve().parents[2]
missing, different, hashed = [], [], 0
files, total = 0, 0
for file in source.rglob('*'):
    if not file.is_file():
        continue
    relative = file.relative_to(source)
    parts = relative.parts
    if '__pycache__' in parts or '.pytest_cache' in parts:
        continue
    files += 1
    total += file.stat().st_size
    copied = target / relative
    if not copied.is_file():
        missing.append(str(relative))
        continue
    mutable = relative.name in {'settings.json', 'relocate_project.py', 'pyvenv.cfg'} or 'Scripts' in parts or relative.suffix == '.log'
    if mutable:
        continue
    if file.stat().st_size != copied.stat().st_size:
        different.append(str(relative))
        continue
    critical = relative.suffix.lower() in {'.pmx', '.vrm', '.exe'} or 'voices' in parts or 'llm-models' in parts
    if critical:
        def digest(path):
            with path.open('rb') as stream:
                return hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest(file) != digest(copied):
            different.append(str(relative))
        hashed += 1
result = {'source_files_checked': files, 'source_bytes': total,
          'critical_files_hashed': hashed, 'missing': missing, 'different': different}
out = target / 'Sakura/audit-results/relocation/inventory.json'
out.write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result), flush=True)
if missing or different:
    sys.exit(1)
