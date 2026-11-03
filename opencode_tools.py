"""Hand one coding subtask to the OpenCode CLI already installed on this PC.

Sakura's own planner models are small, so a multi-file edit is better done by an agent
built for it. OpenCode brings its own providers, its own model list and its own file
tools, which means the subtask leaves Sakura's workspace boundary check only in the sense
that OpenCode will read everything under the folder it is given. That is why the step is
never auto-approved and the exact prompt text is shown for review.
"""
import os
import re
import shutil
from pathlib import Path

MAX_TASK_CHARACTERS = 8000
MIN_TIMEOUT_SECONDS = 30
MAX_TIMEOUT_SECONDS = 1800
DEFAULT_TIMEOUT_SECONDS = 600
_MODEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,149}')


def binary():
    """The OpenCode program, or None when it is not installed here.

    The npm launcher is a .cmd shim, which Windows can start but which hides the real
    program, so the bundled executable is preferred and the shim is only a fallback.
    """
    candidates = [os.environ.get('SAKURA_OPENCODE_BINARY', '')]
    appdata = os.environ.get('APPDATA', '')
    candidates += [str(Path(appdata) / 'npm' / 'node_modules' / 'opencode-ai' / 'bin' / 'opencode.exe')] if appdata else []
    candidates += [str(Path.home() / '.opencode' / 'bin' / 'opencode.exe')]
    for item in candidates:
        if item:
            path = Path(item).expanduser()
            if path.is_file():
                return path
    found = shutil.which('opencode')
    return Path(found) if found else None


def plan(task, model=''):
    """The prompt and model exactly as they will be handed over, or a refusal.

    A prompt that starts with a dash would be read as one of OpenCode's own options --
    --auto would hand it permission to approve its own edits -- so it is refused rather
    than quoted around, because the argv is built without a host shell either way.
    """
    text = str(task or '').strip()
    if not text:
        raise ValueError('Say what OpenCode should do, in one self-contained instruction.')
    if len(text) > MAX_TASK_CHARACTERS:
        raise ValueError('The instruction is %d characters; keep it under %d and point it at the files by name.'
                         % (len(text), MAX_TASK_CHARACTERS))
    if text.startswith('-'):
        raise ValueError('The instruction must not start with a dash, because OpenCode would read it as one of its own options.')
    if any(ord(character) < 9 for character in text):
        raise ValueError('The instruction must not contain control characters.')
    named = str(model or '').strip()
    if named and not _MODEL.fullmatch(named):
        raise ValueError('Name the model as provider/model, for example freellmapi/aion-2.0, or leave it empty for OpenCode’s own default.')
    return {'task': text, 'model': named}


def timeout_seconds(value):
    if value is None:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        requested = int(value)
    except (TypeError, ValueError):
        raise ValueError('Give the budget in whole seconds.') from None
    return min(max(requested, MIN_TIMEOUT_SECONDS), MAX_TIMEOUT_SECONDS)


def program_identity(path):
    """Which OpenCode program was reviewed, without reading it.

    The npm build is a single 202 MB executable, so the sha256 the other tools take over a run
    script is impossible here; size and last write catch a replaced or updated program, and
    either change sends the step back for a fresh review.
    """
    resolved = Path(path).resolve()
    status = resolved.stat()
    return {'program': str(resolved), 'size': status.st_size, 'modified': int(status.st_mtime)}


def storage_dir():
    """The data directory handed to OpenCode as XDG_DATA_HOME for Sakura's own runs.

    OpenCode keeps its session database under XDG_DATA_HOME, and on this PC that database is
    unreadable for every subcommand ("Database is not empty and has no session table"), so a
    delegation died before OpenCode opened a file. Pointing it at a directory of Sakura's makes
    the run work whatever the user's own store is doing, and keeps Sakura's sessions out of the
    history the user browses in their own terminal. Provider configuration and keys stay exactly
    where they are: only the data path moves.
    """
    from config import BASE_DIR
    return BASE_DIR / 'desktop-profile' / 'opencode-data'


def delegate(program, task, cwd, model='', timeout_seconds_value=DEFAULT_TIMEOUT_SECONDS, cancel_event=None):
    """Run one OpenCode turn inside the task folder and return its own report."""
    from agent_runtime import run_process
    argv = [str(program), 'run', task, '--dir', str(cwd)]
    if model:
        argv += ['-m', model]
    budget = timeout_seconds(timeout_seconds_value)
    data_home = storage_dir()
    data_home.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment['XDG_DATA_HOME'] = str(data_home)
    result = run_process(argv, cwd, budget, cancel_event=cancel_event, env=environment)
    result['tool'] = 'opencode.run'
    result['model'] = model or 'OpenCode default'
    result['cwd'] = str(cwd)
    result['data_dir'] = str(data_home)
    result['timeout_seconds'] = budget
    if result.get('timed_out'):
        result['error'] = ('OpenCode was still working after %d seconds, so its process tree was stopped. '
                           'Only what it already wrote to %s survives; raise timeout_seconds or split '
                           'the instruction into smaller steps.' % (budget, cwd))
    elif result.get('cancelled'):
        result['error'] = 'OpenCode was stopped because this task was cancelled or paused.'
    elif not result.get('ok'):
        result['error'] = ('OpenCode exited with code %s. Its output is what it reported, not a claim that '
                           'the work is done.' % result.get('exit_code'))
    else:
        result['note'] = ('OpenCode ran with its own model and file tools inside %s. Its reply describes what it '
                          'did; read or diff the files it names before reporting the work as finished.' % cwd)
    return result
