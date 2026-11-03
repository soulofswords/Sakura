"""Read-only evidence about the app itself: is it alive, in sync with its source, and are its own files still valid.

Nothing here starts a model, writes a file or contacts anything but loopback. Repair actions
live in repair_actions.py; this module only answers "what is actually wrong".
"""
import hashlib
import json
import os
import socket
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler

from config import BASE_DIR
from product import DISPLAY_NAME, EDITION, INSTALLATION_ID, VERSION

# Ports the companion edition scans when it looks for a backend. Probing them
# directly, rather than through gui_server, keeps this read-only: that helper
# rewrites its own global port and can bind a socket.
PORT_RANGE = range(8766, 8777)
TEXT_SUFFIXES = {'.py', '.js', '.mjs', '.css', '.html', '.txt'}
MAX_DRIFT_FILES = 3000
MAX_HASH_BYTES = 8 * 1024 * 1024
MAX_LOG_TAIL_LINES = 40
MAX_STATE_FILES = 60


def identity():
    """Which Sakura this process belongs to, and where its files live."""
    return {'display_name': DISPLAY_NAME, 'edition': EDITION, 'version': VERSION,
            'installation': INSTALLATION_ID, 'root': str(BASE_DIR)}


def source_root():
    """The developer tree this app was refreshed from, or None when it cannot be found.

    Deployed copies reach the source through the directory junctions the local
    refresh creates, so resolving one of those is the only reliable pointer.
    """
    own = BASE_DIR.resolve()
    for name in ('venv', 'models', 'rvc-dependencies'):
        link = BASE_DIR / name
        if not link.exists():
            continue
        try:
            parent = link.resolve().parent
        except OSError:
            continue
        if (parent / 'tools' / 'create-local-products.py').is_file():
            return parent
    return own if (own / 'tools' / 'create-local-products.py').is_file() else None


def _probe(opener, url, timeout):
    parsed = urlsplit(url)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1'):
        return {'url': url, 'state': 'refused', 'reason': 'Only loopback probes are allowed.'}
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout):
            pass
    except OSError:
        return {'url': url, 'state': 'closed'}
    try:
        with opener.open(url, timeout=timeout) as response:
            body = response.read(4096)
        return {'url': url, 'state': 'open', 'status': getattr(response, 'status', 200),
                'body': body[:1200].decode('utf-8', 'replace')}
    except OSError:
        return {'url': url, 'state': 'listening', 'reason': 'Accepts connections but did not answer.'}


def liveness(timeout=0.4):
    """Which loopback ports currently answer, and whether each one is really this app."""
    opener = build_opener(ProxyHandler({}))
    backends = []
    for port in PORT_RANGE:
        url = 'http://127.0.0.1:%d/api/identity' % port
        item = _probe(opener, url, timeout)
        if item['state'] in ('closed', 'refused'):
            continue
        record = {'port': port, 'state': item['state']}
        if item['state'] == 'open':
            try:
                payload = json.loads(item['body'])
            except ValueError:
                payload = {}
            same = (payload.get('application') == 'sakura-anime-assistant'
                    and payload.get('edition') == EDITION
                    and payload.get('installation') == INSTALLATION_ID)
            record.update(sakura=payload.get('application') == 'sakura-anime-assistant',
                          edition=payload.get('edition'),
                          same_installation=payload.get('installation') == INSTALLATION_ID,
                          this_app=same)
            if not same and payload.get('application') == 'sakura-anime-assistant':
                record['reason'] = 'A different Sakura copy or edition answers this port.'
            elif payload.get('application') != 'sakura-anime-assistant':
                record['reason'] = 'Something that is not Sakura holds this port.'
        else:
            record['reason'] = item.get('reason', '')
        backends.append(record)
    listening = [item for item in backends if item['state'] == 'open' and item.get('this_app')]
    other = [item['port'] for item in backends if item.get('sakura') and not item.get('this_app')]
    return {'backends': backends, 'healthy_backend_count': len(listening),
            'other_installation_ports': other,
            'ports_exhausted': len([item for item in backends if item['state'] != 'closed']) >= len(PORT_RANGE),
            'note': 'healthy_backend_count above 1 means more than one window is running against this installation.'}


def _tracked_text_files(root):
    """Files the local refresh copies file-for-file, excluding junctioned payloads."""
    found = []
    for path in sorted(root.glob('*.py')):
        found.append(path)
    for name in ('requirements.txt', 'requirements-agent.txt', 'requirements-rvc.txt'):
        candidate = root / name
        if candidate.is_file():
            found.append(candidate)
    static = root / 'static'
    if static.is_dir():
        for path in sorted(static.rglob('*')):
            if not path.is_file() or path.suffix.casefold() not in TEXT_SUFFIXES:
                continue
            if any(part.lower() in ('node_modules', '__pycache__') for part in path.parts):
                continue
            found.append(path)
    return found


def _digest(path):
    digest = hashlib.sha256()
    try:
        size = path.stat().st_size
        if size > MAX_HASH_BYTES:
            return None, size
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
    except OSError:
        return None, None
    return digest.hexdigest(), size


def drift(limit=MAX_DRIFT_FILES):
    """Text files whose app copy differs from or is absent in the source tree.

    This is the evidence behind "I changed it and nothing happened": the running
    app is a refreshed copy, so a newer source file can simply never have arrived.
    """
    own = BASE_DIR.resolve()
    source = source_root()
    if source is None:
        return {'comparable': False, 'reason': 'This copy has no reachable source tree, so it cannot be compared.'}
    if source == own:
        return {'comparable': False, 'running_from_source': True,
                'source': str(source),
                'reason': 'This app is running the source tree itself, so there is no deployed copy to fall behind.'}
    checked = 0
    stale, missing, extra = [], [], []
    for path in _tracked_text_files(source):
        if checked >= limit:
            break
        checked += 1
        relative = path.relative_to(source)
        target = own / relative
        source_hash, _ = _digest(path)
        if source_hash is None:
            continue
        if not target.is_file():
            missing.append(str(relative))
            continue
        target_hash, _ = _digest(target)
        if target_hash != source_hash:
            entry = {'path': str(relative), 'source_mtime': int(path.stat().st_mtime),
                     'app_mtime': int(target.stat().st_mtime)}
            entry['newer_in_source'] = entry['source_mtime'] > entry['app_mtime']
            stale.append(entry)
    for path in _tracked_text_files(own):
        if not (source / path.relative_to(own)).is_file():
            extra.append(str(path.relative_to(own)))
    # The local refresh deliberately rewrites these for the edition, so a difference
    # there is expected and must not be reported as the copy falling behind.
    transformed = {'static/index.html', 'static/js/app.js'}
    entry_map = lambda item: item['path'].replace('\\', '/').casefold()
    expected = [item for item in stale if entry_map(item) in transformed]
    real = [item for item in stale if entry_map(item) not in transformed]
    return {'comparable': True, 'source': str(source), 'app': str(own), 'files_checked': checked,
            'missing_in_app': missing[:60], 'missing_count': len(missing),
            'stale_in_app': real[:60],
            'stale_count': len(real),
            'edition_transformed_files': sorted({item['path'] for item in expected}),
            'only_in_app': extra[:40],
            'out_of_date': bool(missing) or any(item['newer_in_source'] for item in real)}


def _json_state(path):
    try:
        text = path.read_text(encoding='utf-8')
    except OSError as error:
        return {'readable': False, 'reason': type(error).__name__}
    stripped = text.lstrip('﻿ ')
    try:
        value = json.loads(stripped)
        return {'readable': True, 'kind': type(value).__name__, 'items': len(value) if isinstance(value, (list, dict)) else None}
    except ValueError as error:
        return {'readable': False, 'reason': 'Malformed JSON: ' + str(error)[:200],
                'salvageable': salvage_json(stripped) is not None}


def salvage_json(text, attempts=400):
    """Largest recoverable JSON value from a truncated or trailing-garbage file, else None.

    A kill during a write usually cuts the tail off, so closing the brackets that
    were still open at the last complete member normally restores the real data.
    Only the last few hundred safe cut points are tried, so a large file stays cheap.
    """
    for candidate in (text, text.lstrip('﻿ ')):
        try:
            return json.loads(candidate)
        except ValueError:
            pass
    body = text.lstrip('﻿ ')
    stack = []
    cuts = []
    inside = escaped = False
    for index, character in enumerate(body):
        if inside:
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == '"':
                inside = False
            continue
        if character == '"':
            inside = True
        elif character in '[{':
            stack.append(character)
        elif character in ']}':
            if not stack:
                break
            stack.pop()
            # A closing bracket ends one complete value, so the document can be
            # closed here by adding whatever its ancestors still left open.
            cuts.append((index + 1, list(stack)))
        elif character == ',' and len(stack) == 1:
            # A comma at the outer level follows a complete member of the root
            # value, which is the other place a half-written tail can be cut.
            cuts.append((index, list(stack)))
    for cut, openers in reversed(cuts[-attempts:]):
        closers = ('}' if item == '{' else ']' for item in reversed(openers))
        try:
            value = json.loads(body[:cut] + ''.join(closers))
        except ValueError:
            continue
        return value
    return None


def _sqlite_state(path):
    try:
        uri = 'file:' + path.as_posix() + '?mode=ro'
        with sqlite3.connect(uri, uri=True, timeout=2) as connection:
            rows = [str(row[0]) for row in connection.execute('PRAGMA integrity_check').fetchmany(4)]
            tables = [row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchmany(40)]
        return {'readable': True, 'integrity': rows[:3], 'ok': rows == ['ok'], 'tables': len(tables)}
    except sqlite3.Error as error:
        return {'readable': False, 'reason': str(error)[:200], 'ok': False}


def state():
    """Validity of Sakura's own persisted files, plus leftovers from an interrupted write."""
    candidates = []
    for pattern in ('settings.json', 'desktop-profile/*.json', 'desktop-profile/*.sqlite3',
                    'desktop-profile/*/*.json'):
        candidates.extend(sorted(BASE_DIR.glob(pattern)))
    candidates = [path for path in candidates if path.is_file()][:MAX_STATE_FILES]
    files = []
    broken = 0
    for path in candidates:
        record = {'path': str(path.relative_to(BASE_DIR)), 'bytes': path.stat().st_size}
        if path.suffix.casefold() == '.json':
            record.update(_json_state(path))
        elif path.suffix.casefold() in ('.sqlite3', '.db'):
            record.update(_sqlite_state(path))
        if not record.get('readable', True) or record.get('ok') is False:
            broken += 1
            record['repairable'] = True
        files.append(record)
    now = time.time()
    leftovers = []
    for path in sorted((BASE_DIR / 'desktop-profile').rglob('*'))[:4000]:
        try:
            if not path.is_file() or not path.name.endswith('.tmp'):
                continue
            age = now - path.stat().st_mtime
        except OSError:
            continue
        # Sakura publishes state by swapping a dot-prefixed temporary into
        # place, so a surviving temporary file means some write never finished.
        leftovers.append({'path': str(path.relative_to(BASE_DIR)), 'age_seconds': int(age),
                          'bytes': path.stat().st_size})
    crash_log = BASE_DIR / 'logs' / 'desktop-crash.log'
    return {'files': files, 'broken_count': broken, 'write_leftovers': leftovers[:20],
            'crash_log': {'present': crash_log.is_file(),
                          'bytes': crash_log.stat().st_size if crash_log.is_file() else 0}}


def _tail(path, lines):
    try:
        with path.open('rb') as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 64 * 1024))
            data = handle.read().decode('utf-8', 'replace').splitlines()
        return data[-lines:]
    except OSError:
        return []


def logs(lines=MAX_LOG_TAIL_LINES):
    """The last lines of Sakura's own logs, with obvious failures counted."""
    directory = BASE_DIR / 'logs'
    items = []
    if not directory.is_dir():
        return {'files': [], 'note': 'No logs folder yet.'}
    for path in sorted(directory.glob('*.log'), key=lambda item: item.stat().st_mtime, reverse=True)[:8]:
        content = _tail(path, lines)
        problems = [line for line in content if any(marker in line for marker in
                    ('Traceback', 'ERROR', 'Error', 'FAILED', 'Exception', 'refused', 'timed out'))]
        items.append({'path': str(path.relative_to(BASE_DIR)), 'bytes': path.stat().st_size,
                      'modified': int(path.stat().st_mtime), 'lines_returned': len(content),
                      'recent_problem_lines': problems[-10:], 'tail': content[-10:]})
    return {'files': items}


def backups(limit=20):
    """Repairs that have run, newest first, each with the files it saved."""
    root = BASE_DIR / 'logs' / 'repair-backups'
    if not root.is_dir():
        return {'directory': str(root), 'backups': [], 'note': 'No repair has run yet.'}
    folders = sorted((path for path in root.iterdir() if path.is_dir()), reverse=True)[:limit]
    return {'directory': str(root),
            'backups': [{'folder': path.name,
                         'files': [{'path': str(item.relative_to(path)), 'bytes': item.stat().st_size}
                                   for item in sorted(path.rglob('*')) if item.is_file()][:40]}
                        for path in folders]}


def engines(include_http=True):
    """Local speech, voice-changer and inference state, read without starting anything."""
    summary = {}
    try:
        from agent_local_ai import local_ai
        status = local_ai.status()
        summary['inference'] = {'models': len(status.get('models') or []), 'loaded': status.get('loaded'),
                                'job_running': bool((status.get('job') or {}).get('running')),
                                'engine': status.get('engine'), 'backend': status.get('backend'),
                                'runtimes': status.get('runtimes')}
    except Exception as error:
        summary['inference'] = {'error': type(error).__name__}
    try:
        from kokoro_speech import status as kokoro
        summary['speech'] = {key: kokoro().get(key) for key in ('phase', 'message', 'progress')}
    except Exception as error:
        summary['speech'] = {'error': type(error).__name__}
    try:
        from config import RVC_SERVER_URL
        if include_http:
            summary['voice_changer'] = _probe(build_opener(ProxyHandler({})), RVC_SERVER_URL + '/', 0.4)
        else:
            summary['voice_changer'] = {'url': RVC_SERVER_URL, 'state': 'skipped'}
    except Exception as error:
        summary['voice_changer'] = {'error': type(error).__name__}
    if include_http:
        from sakura_doctor import local_health
        endpoints = {}
        try:
            from config import OLLAMA_BASE_URL
            endpoints['ollama'] = OLLAMA_BASE_URL + '/api/tags'
        except Exception:
            pass
        try:
            from config import GPT_SOVITS_URL
            endpoints['gpt_sovits'] = GPT_SOVITS_URL + '/'
        except Exception:
            pass
        if endpoints:
            summary['engine_endpoints'] = local_health(endpoints)
    try:
        import psutil
        summary['memory'] = {'available_gib': round(psutil.virtual_memory().available / 1024 ** 3, 2),
                             'used_percent': psutil.virtual_memory().percent}
    except Exception as error:
        summary['memory'] = {'error': type(error).__name__}
    return summary


def snapshot(sections=None, include_http=True):
    """Bounded read-only picture of the app. Section names are stable for the agent prompt."""
    wanted = [item for item in (sections or ['liveness', 'drift', 'state', 'engines', 'logs'])]
    builders = {'liveness': liveness, 'drift': drift, 'state': state, 'logs': logs, 'backups': backups}
    result = {'identity': identity()}
    problems = []
    for name in ('liveness', 'drift', 'state', 'engines', 'logs', 'backups'):
        if name not in wanted:
            continue
        try:
            value = engines(include_http=include_http) if name == 'engines' else builders[name]()
        except Exception as error:
            value = {'error': type(error).__name__ + ': ' + ' '.join(str(error).split())[:200]}
        result[name] = value
    drift_data = result.get('drift') or {}
    state_data = result.get('state') or {}
    live = result.get('liveness') or {}
    if drift_data.get('out_of_date'):
        problems.append('The running copy is out of date with its source tree.')
    if state_data.get('broken_count'):
        problems.append('A saved-state file cannot be read; the app silently uses defaults instead.')
    if live.get('healthy_backend_count', 0) == 0:
        if live.get('other_installation_ports'):
            problems.append('A Sakura from a different installation folder holds '
                            + ', '.join(str(port) for port in live['other_installation_ports'])
                            + ', so this copy may be talking to that window instead of its own.')
        else:
            problems.append('No Sakura backend answers on its own ports.')
    if live.get('healthy_backend_count', 0) > 1:
        problems.append('More than one window is running against this installation.')
    if state_data.get('write_leftovers'):
        problems.append('An interrupted write left temporary files behind.')
    result['problems'] = problems
    return result
