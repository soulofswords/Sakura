"""Persistent, per-model rig overrides kept with the user's model library."""
import hashlib
import json
from pathlib import Path
import threading
import uuid

_lock = threading.Lock()


def _paths(root, model):
    root = Path(root).resolve()
    if not isinstance(model, str) or len(model) > 2048:
        raise ValueError('Choose a model inside the models folder.')
    file = (root / model.replace('\\', '/')).resolve()
    if not file.is_relative_to(root) or file.suffix.lower() not in {'.pmx', '.vrm'} or not file.is_file():
        raise ValueError('Choose an existing PMX or VRM model inside the models folder.')
    key = file.relative_to(root).as_posix()
    directory = (root / '.sakura' / 'rig-repairs').resolve()
    if not directory.is_relative_to(root):
        raise ValueError('Repair storage must remain inside the models folder.')
    target = directory / (hashlib.sha256(key.encode('utf-8')).hexdigest() + '.json')
    if not target.resolve().is_relative_to(root):raise ValueError('Repair storage must remain inside the models folder.')
    stat = file.stat()
    fingerprint = [stat.st_size, stat.st_mtime_ns]
    return key, target, fingerprint


def _validated(repairs):
    if not isinstance(repairs, dict):raise ValueError('Provide valid bone repairs.')
    manual = repairs.get('manual', [])
    if not isinstance(manual, list) or len(manual) > 10000 or any(not isinstance(s, str) or len(s)>1024 for s in manual):
        raise ValueError('Provide a valid manual bone list.')
    report = repairs.get('diagnostic')
    if report is not None:
        if not isinstance(report, dict) or not isinstance(report.get('signature'), str) or len(report['signature'])>2000000:
            raise ValueError('Provide a valid rig signature.')
        frozen = report.get('frozen')
        if not isinstance(frozen, list) or len(frozen)>10000 or any(type(i) is not int or not 0<=i<100000 for i in frozen):
            raise ValueError('Provide valid frozen bone indices.')
        report = {'version': report.get('version',2), 'signature': report['signature'], 'frozen': sorted(set(frozen))}
    return {'manual': sorted(set(manual)), 'diagnostic': report}


def read_repairs(root, model):
    key, target, fingerprint = _paths(root, model)
    with _lock:
        if not target.is_file():return {'model':key, 'repairs':None, 'invalidated':False}
        data = json.loads(target.read_text(encoding='utf-8'))
    if data.get('fingerprint') != fingerprint or data.get('model') != key:
        return {'model':key, 'repairs':None, 'invalidated':True}
    return {'model':key, 'repairs':_validated(data.get('repairs')), 'invalidated':False}


def write_repairs(root, model, repairs):
    key, target, fingerprint = _paths(root, model)
    repairs = _validated(repairs)
    with _lock:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix('.'+uuid.uuid4().hex+'.tmp')
        try:
            temporary.write_text(json.dumps({'model':key,'fingerprint':fingerprint,'repairs':repairs},ensure_ascii=False),encoding='utf-8')
            temporary.replace(target)
        finally:temporary.unlink(missing_ok=True)
    return {'saved':True, 'model':key}
