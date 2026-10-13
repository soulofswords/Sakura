"""Repair project-local paths and virtualenv entry points after a Windows copy."""
import json
import re
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
old = Path(sys.argv[1])
new = root.parent
changes = []
settings_file = root / 'settings.json'
settings = json.loads(settings_file.read_text(encoding='utf-8-sig'))

def relocate(value):
    if isinstance(value, dict):
        return {k: relocate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [relocate(v) for v in value]
    if isinstance(value, str) and value.lower().startswith(str(old).lower()):
        return str(new) + value[len(str(old)):]
    return value

updated = relocate(settings)
if (root / 'llm-models' / 'blobs').is_dir() and updated.get('ollama_models_folder', '').lower().startswith(str(new).lower()):
    updated['ollama_models_folder'] = 'llm-models'
if settings != updated:
    settings_file.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding='utf-8')
    changes.append('settings.json')

for name in ['venv', 'rvc-venv', 'rvc-runtime', 'rvc-gpu-runtime']:
    env = root / name
    scripts = env / 'Scripts'
    interpreter = scripts / 'python.exe'
    if not interpreter.is_file():
        continue
    cfg = env / 'pyvenv.cfg'
    if cfg.is_file():
        content = cfg.read_text(encoding='utf-8')
        fixed = content.replace(str(old / 'Sakura' / name), str(env)).replace(str(old / name), str(env))
        if fixed != content:
            cfg.write_text(fixed, encoding='utf-8')
            changes.append(str(cfg.relative_to(root)))
    for file in scripts.iterdir():
        if not file.is_file() or file.stat().st_size > 2_000_000 or file.name.lower().startswith('python'):
            continue
        data = file.read_bytes()
        fixed = data
        if file.suffix.lower() == '.exe':
            # distlib console launchers carry the interpreter in an appended
            # shebang before their ZIP. ZIP supports the changed prefix length.
            matches = [match for match in re.finditer(rb'#![^\r\n]+', data)
                       if str(old).lower().encode() in match.group().lower()]
            at = matches[-1].start() if matches else -1
            end = data.find(b'\n', at) if at >= 0 else -1
            if end > at and str(old).lower().encode() in data[at:end].lower():
                fixed = data[:at] + ('#!"' + str(interpreter) + '"\n').encode('utf-8') + data[end+1:]
        elif file.suffix.lower() in {'.bat', '.ps1', '.py', ''}:
            fixed = data.replace(str(old / 'Sakura' / name).encode(), str(env).encode()).replace(str(old / name).encode(), str(env).encode())
        if fixed != data:
            file.write_bytes(fixed)
            changes.append(str(file.relative_to(root)))

report = root / 'audit-results' / 'relocation'
report.mkdir(parents=True, exist_ok=True)
history = report / 'path-repairs.json'
previous = json.loads(history.read_text()) if history.exists() else []
history.write_text(json.dumps(sorted(set(previous + changes)), indent=2), encoding='utf-8')
print(json.dumps({'updated': len(changes), 'project': str(root)}))
