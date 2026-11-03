"""The bounded ways Sakura is allowed to change itself.

Every entry here is proposed to the user with the exact files and diffs first, and
each one copies what it replaces into logs/repair-backups before touching it.
Nothing in this module restarts, closes or signals the running app.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import repair_diagnostics as diagnostics
from atomic_state import atomic_text
from config import BASE_DIR
from product import EDITION

BACKUP_ROOT = BASE_DIR / 'logs' / 'repair-backups'
PATCH_SUFFIXES = {'.py', '.js', '.mjs', '.css', '.html', '.txt'}
LOCKED_FIRST_PARTS = {'models', 'voices', 'venv', 'kokoro-assets', 'llm-models', 'ollama-runtime',
                      'rvc-assets', 'rvc-dependencies', 'rvc-extra', 'rvc-gpu-runtime', 'rvc-runtime',
                      'rvc-venv', 'rvc-amd-runtime', 'agent-integrations', 'tools', 'backups',
                      'node_modules', 'logs', '__pycache__'}
# A rebuilt settings.json stays empty because app.get_settings() layers it over its
# own factory defaults; the other files are read in a specific shape.
EMPTY_STATE = {'settings.json': {},
               'desktop-profile/agent-skills.json': [],
               'desktop-profile/agent-learning.json': {'version': 1, 'enabled': True, 'notes': '',
                                                       'profile': '', 'procedures': [], 'seen': []},
               'desktop-profile/agent-task-history.json': {'version': 1, 'runs': []}}
RECREATABLE_DATABASES = {'desktop-profile/agent-task-history.sqlite3', 'desktop-profile/agent-knowledge.sqlite3'}
MAX_REFRESH_SECONDS = 900


def _key(relative):
    return str(relative).replace('\\', '/').casefold()


def _resolve(relative):
    path = Path(str(relative))
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Use a path relative to the app folder; absolute paths and .. are refused.')
    if path.parts and path.parts[0].lower() in LOCKED_FIRST_PARTS:
        raise ValueError('That folder holds models, runtimes or logs shared with other copies. Repair only source and static files.')
    resolved = (BASE_DIR / path).resolve(strict=False)
    if not resolved.is_relative_to(BASE_DIR.resolve(strict=False)):
        raise ValueError('The path leaves the app folder through a link or junction; repairing it would change another installation.')
    return resolved


def patchable(relative):
    """Only the app's own code and assets, never the guard rails that decide approval."""
    path = Path(str(relative))
    if _key(path) in ('repair_actions.py', 'repair_diagnostics.py', 'agent_permissions.py', 'command_approval.py'):
        return False
    if path.suffix.casefold() not in PATCH_SUFFIXES:
        return False
    if len(path.parts) == 1:
        return path.suffix.casefold() == '.py' or path.name.startswith('requirements')
    return _key(path).startswith('static/')


# App-owned state, matched as path prefixes so WebView profile stores and model
# folders can never be selected for a rebuild.
REPAIRABLE_STATE = ('settings.json', 'desktop-profile/agent-', 'desktop-profile/companion-placement.json',
                    'desktop-profile/user_prefs.json', 'desktop-profile/starter-skills-v1.json',
                    'desktop-profile/starter-skills-v2.json',
                    'desktop-profile/pre-colibri-default.json')


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def _file_digest(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def backups(limit=20):
    """What earlier repairs saved, newest first, so any change can be undone."""
    return diagnostics.backups(limit)


def _stamp():
    return time.strftime('%Y%m%d-%H%M%S')


def _copy_backup(path):
    relative = path.relative_to(BASE_DIR) if path.is_relative_to(BASE_DIR) else Path(path.name)
    destination = BACKUP_ROOT / _stamp() / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
    return destination


def plan_patch(relative, replacements=None, patch_text=None):
    """Review-only: build the exact diff and lock it to the current file hash."""
    import agent_workspace_files as files
    path = _resolve(relative)
    if not patchable(relative):
        raise ValueError('Repair may change only the app source .py files, static assets and requirements text.')
    if not path.is_file():
        raise ValueError('That file is not in this app folder. Use app.files.sync to bring a missing source file in.')
    if replacements and patch_text:
        raise ValueError('Choose either exact replacements or one unified diff, not both.')
    if not replacements and not patch_text:
        raise ValueError('Supply replacements or patch_text describing the repair.')
    prepared = files.prepare_edit(path, replacements) if replacements else files.prepare_patch(path, patch_text)
    return {'kind': 'patch', 'path': str(path), 'relative': _key(relative),
            'arguments': prepared['arguments'], 'bindings': prepared['bindings'],
            'base_sha256': prepared['bindings']['base_sha256'],
            'digest': _digest({'kind': 'patch', 'path': str(path), 'base': prepared['bindings']['base_sha256'],
                               'result': prepared['bindings']['result_sha256']}),
            'preview': dict(prepared['preview'],
                            operation='Repair one app file',
                            backup='the current file is copied to logs/repair-backups first',
                            warning='Changes the code of the app itself. It takes effect only after the app is restarted, '
                                    'and this step never restarts anything. The file hash is re-checked before writing.')}


def state_files():
    """The state files this app actually has, with whether each one still reads."""
    return diagnostics.state()


def plan_state(relative, mode, empty_kind=None, backup=None):
    """Review-only: decide exactly what text a state repair will write, or that it will remove the file."""
    path = _resolve(relative)
    key = _key(relative)
    if not key.endswith('.json') and not key.endswith('.sqlite3'):
        raise ValueError('Repair only JSON or database state files.')
    if not key.startswith(REPAIRABLE_STATE):
        raise ValueError('That is browser or runtime storage, not app state the repair may rewrite.')
    known = {_key(item['path']) for item in state_files().get('files', [])}
    if key not in known:
        raise ValueError('Repair only the state files that app.diagnostics lists for this app.')
    if not path.is_file():
        raise ValueError('That state file is not present, so there is nothing to repair.')
    base = _file_digest(path)
    write = None
    note = ''
    if mode == 'salvage':
        if path.suffix.casefold() != '.json':
            raise ValueError('Salvaging partial text works on JSON state files only.')
        value = diagnostics.salvage_json(path.read_text(encoding='utf-8', errors='replace'))
        if value is None:
            raise ValueError('No recoverable JSON was found. Choose rebuild, restore or recreate instead.')
        write = json.dumps(value, ensure_ascii=False)
        note = 'keeps the ' + str(len(value) if isinstance(value, (list, dict)) else 'recovered') + ' readable entries and drops the damaged tail'
    elif mode == 'rebuild':
        replacement = EMPTY_STATE.get(key)
        if replacement is None and empty_kind == 'array':
            replacement = []
        elif replacement is None and empty_kind == 'object':
            replacement = {}
        if replacement is None:
            raise ValueError('This file has no known empty shape. Pass empty_kind object or array, or restore a backup.')
        write = json.dumps(replacement, ensure_ascii=False)
        note = 'replaces it with the shape this app reads; anything the app could not parse is already lost to it'
    elif mode == 'recreate':
        if key not in RECREATABLE_DATABASES:
            raise ValueError('Only the task-history and knowledge databases are removed for the app to recreate.')
        write = None
        note = 'removes the damaged database so the app creates a fresh one'
    elif mode == 'restore':
        if path.suffix.casefold() != '.json':
            raise ValueError('Restoring a saved copy works on JSON state files only.')
        saved = _backup_path(backup)
        record = diagnostics._json_state(saved)
        if not record.get('readable'):
            raise ValueError('That saved copy is itself unreadable, so restoring it would change nothing useful.')
        write = saved.read_text(encoding='utf-8')
        note = 'restores ' + str(saved)
    else:
        raise ValueError('Choose salvage, rebuild, recreate or restore.')
    return {'kind': 'state', 'path': str(path), 'relative': key, 'mode': mode, 'base_sha256': base,
            'write': write, 'digest': _digest({'path': str(path), 'mode': mode, 'base': base, 'write': write}),
            'preview': {'operation': 'Repair one saved-state file', 'path': str(path),
                        'current': diagnostics._json_state(path) if path.suffix.casefold() == '.json'
                        else diagnostics._sqlite_state(path),
                        'effect': note, 'writes_bytes': len(write.encode('utf-8')) if write is not None else 0,
                        'backup': 'the file as it stands now is copied to logs/repair-backups first',
                        'warning': 'A state file the app cannot read is already invisible to it, so a repair can only stop '
                                   'the silence or recover what still parses. Nothing is restarted.'}}


def _backup_path(backup):
    """One file inside logs/repair-backups, named by the backups listing."""
    if not backup:
        raise ValueError('Name the saved copy to restore, from the backups listing.')
    path = Path(str(backup))
    if not path.is_absolute():
        path = BACKUP_ROOT / path
    root = BACKUP_ROOT.resolve(strict=False)
    resolved = path.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ValueError('Restore only from a file under logs/repair-backups.')
    if not resolved.is_file():
        raise ValueError('That saved copy is not on disk.')
    return resolved


def plan_sync(relative_paths):
    """Review-only: name the source files the running copy is missing or holding stale."""
    source = diagnostics.source_root()
    own = BASE_DIR.resolve()
    if source is None or source == own:
        raise ValueError('This app is the source tree itself, so there is nothing to sync into it.')
    changes = []
    for relative in relative_paths:
        path = Path(str(relative))
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Use paths relative to the app folder.')
        origin = source / path
        if not origin.is_file():
            raise ValueError('That file is not in the source tree: ' + str(relative))
        if origin.suffix.casefold() not in PATCH_SUFFIXES:
            raise ValueError('app.files.sync copies text source files only.')
        target = own / path
        origin_hash = _file_digest(origin)
        target_hash = _file_digest(target) if target.is_file() else None
        changes.append({'path': _key(path), 'source': str(origin), 'target': str(target),
                        'source_sha256': origin_hash, 'target_sha256': target_hash,
                        'state': 'missing' if target_hash is None else 'stale' if target_hash != origin_hash else 'already current'})
    fresh = [item for item in changes if item['state'] != 'already current']
    if not fresh:
        raise ValueError('Those files already match the source tree, so syncing them would change nothing.')
    return {'kind': 'sync', 'changes': changes, 'digest': _digest([item['path'] + item['source_sha256'] for item in fresh]),
            'preview': {'operation': 'Copy reviewed source files into the running app',
                        'files': [{'path': item['path'], 'state': item['state'],
                                   'source_sha256': item['source_sha256'][:16],
                                   'app_sha256': (item['target_sha256'] or '')[:16]} for item in changes],
                        'warning': 'Overwrites only these files in the app folder, after copying each one it replaces to '
                                   'logs/repair-backups. A file the running window holds open is reported, not forced. '
                                   'The app still needs a restart to load it.'}}


def plan_refresh(edition=None):
    """Review-only: describe the full local refresh that rebuilds the deployed copies."""
    source = diagnostics.source_root()
    if source is None:
        raise ValueError('No source tree is reachable, so the app cannot be refreshed from one.')
    script = source / 'tools' / 'create-local-products.py'
    if not script.is_file():
        raise ValueError('The refresh script is missing from the source tree.')
    chosen = edition or EDITION
    if chosen not in ('companion', 'vtuber'):
        raise ValueError('Refresh one edition at a time: companion or vtuber.')
    return {'kind': 'refresh', 'script': str(script), 'edition': chosen, 'source': str(source),
            'digest': _digest({'script': str(script), 'edition': chosen}),
            'preview': {'operation': 'Refresh this app from its source tree', 'edition': chosen,
                        'source': str(source), 'app': str(BASE_DIR),
                        'command': ' '.join([sys.executable, str(script), '--edition', chosen]),
                        'warning': 'Rebuilds the launcher and copies every app file for the edition. It can take several minutes, '
                                   'fails on files the running window still locks, and changes nothing the app uses until a restart.'}}


def files_execute(path, prepared):
    import agent_workspace_files as files
    return files.execute_prepared(path, prepared)


def _reprepare(plan, path):
    import agent_workspace_files as files
    arguments = plan.get('arguments') or {}
    if 'replacements' in arguments:
        return files.prepare_edit(path, arguments['replacements'])
    return files.prepare_patch(path, arguments['patch_text'])


def apply(plan, cancel_event=None):
    """The single write path. Re-verifies what the user approved, backs up, then acts."""
    if cancel_event is not None and cancel_event.is_set():
        return {'ok': False, 'cancelled': True, 'error': 'Cancelled before execution.'}
    kind = plan.get('kind')
    if kind == 'patch':
        path = Path(plan['path'])
        if not path.is_file() or _file_digest(path) != plan['base_sha256']:
            return {'ok': False, 'error': 'That file changed after review. Nothing was written; propose the repair again.'}
        saved = _copy_backup(path)
        try:
            result = files_execute(path, _reprepare(plan, path))
        except ValueError as error:
            return {'ok': False, 'error': str(error)[:400], 'backup': str(saved)}
        return {'ok': True, 'changed': str(path), 'backup': str(saved), 'bytes': result['bytes'],
                'sha256': result['sha256'], 'restart_required': True,
                'message': 'The file on disk is repaired. Nothing was restarted, so the running window still uses the old code.'}
    if kind == 'state':
        path = Path(plan['path'])
        if not path.is_file() or _file_digest(path) != plan['base_sha256']:
            return {'ok': False, 'error': 'That state file changed after review. Nothing was written; propose the repair again.'}
        saved = _copy_backup(path)
        if plan['mode'] == 'recreate':
            path.unlink()
            return {'ok': True, 'removed': str(path), 'backup': str(saved),
                    'message': 'Removed the damaged database so the app can create a fresh one. The original is saved.'}
        if plan['write'] is None:
            return {'ok': False, 'error': 'The reviewed repair had no content to write. Nothing was written.'}
        atomic_text(path, plan['write'])
        verbs = {'salvage': 'Recovered the readable part of', 'rebuild': 'Wrote', 'restore': 'Restored'}
        return {'ok': True, 'repaired': str(path), 'backup': str(saved),
                'message': verbs.get(plan['mode'], 'Repaired') + ' the state file. '
                           + ('The unreadable original is saved at ' + str(saved) + '.' if plan['mode'] != 'restore'
                              else 'The damaged current file is saved at ' + str(saved) + '.')}
    if kind == 'sync':
        written, failed = [], []
        for item in plan['changes']:
            if item['state'] == 'already current':
                continue
            source = Path(item['source'])
            target = Path(item['target'])
            if _file_digest(source) != item['source_sha256']:
                return {'ok': False, 'error': 'The source file changed after review. Nothing more was copied.', 'copied': written}
            saved = None
            if target.is_file():
                if _file_digest(target) != item['target_sha256']:
                    failed.append({'path': item['path'], 'reason': 'the app copy changed after review'})
                    continue
                saved = str(_copy_backup(target))
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(source, target)
            except OSError:
                failed.append({'path': item['path'], 'reason': 'the running app holds this file open'})
                continue
            written.append({'path': item['path'], 'backup': saved,
                            'verified': _file_digest(target) == item['source_sha256']})
        unverified = [item['path'] for item in written if not item['verified']]
        message = (('Copied ' + str(len(written)) + ' file(s) into the app folder. Nothing was restarted, so the window '
                    'still runs the previous code until it starts again.') if written else 'Nothing was copied.')
        if unverified:
            message += ' Not verified after copying: ' + ', '.join(unverified) + '.'
        if failed:
            message += ' Not copied: ' + ', '.join(item['path'] + ' (' + item['reason'] + ')' for item in failed) + '.'
        return {'ok': bool(written) and not unverified, 'copied': written, 'failed': failed,
                'restart_required': bool(written), 'message': message}
    if kind == 'refresh':
        try:
            process = subprocess.run([sys.executable, plan['script'], '--edition', plan['edition']],
                                     cwd=plan['source'], capture_output=True, text=True,
                                     encoding='utf-8', errors='replace', timeout=MAX_REFRESH_SECONDS)
        except subprocess.TimeoutExpired:
            return {'ok': False, 'error': 'The refresh ran past ' + str(MAX_REFRESH_SECONDS) +
                     ' seconds and was stopped. Check the app folder for a partial copy.'}
        except OSError as error:
            return {'ok': False, 'error': 'The refresh could not start: ' + str(error)[:200]}
        return {'ok': process.returncode == 0, 'returncode': process.returncode,
                'output': (process.stdout or '').strip().splitlines()[-8:],
                'errors': (process.stderr or '').strip().splitlines()[-8:], 'restart_required': True,
                'message': ('The source tree was refreshed into the app folder. Nothing was restarted.'
                            if process.returncode == 0 else
                            'The refresh failed, so anything it refused is unchanged. A locked file usually means this '
                            'window is still running; closing it and refreshing again is the usual fix.')}
    return {'ok': False, 'error': 'Unknown repair kind.'}
