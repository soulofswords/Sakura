"""Shallow clone of a public HTTPS repository into a task workspace. Nothing is executed."""
import re
import shutil
import subprocess
from pathlib import Path

# https only, no userinfo, query or fragment. The scheme prefix plus the explicit `--`
# separator means a crafted value can never reach git as an option or an ext:: transport.
REPO_URL = re.compile(
    r'https://(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,24}'
    r'/[A-Za-z0-9._~-]{1,100}(?:/[A-Za-z0-9._~-]{1,100}){1,3}(?:\.git)?/?\Z')
# Measured on this PC: a shallow clone of a 207 MB repository with 2246 files took 40 seconds,
# so 300 leaves room for a slow link without letting a dead download sit on the step forever.
MAX_CLONE_SECONDS = 300
MAX_REPORTED_FILES = 5000


def git_executable():
    found = shutil.which('git')
    if not found:
        raise ValueError('Git is not installed or not on PATH, so Sakura cannot clone a repository. '
                         'Install Git, or put the files in the workspace yourself.')
    return found


def validate_url(url):
    if not isinstance(url, str) or not REPO_URL.fullmatch(url.strip()):
        raise ValueError('Clone needs a public https:// repository URL without credentials, query or fragment.')
    return url.strip().rstrip('/')


def plan(url, folder):
    """Validate a clone request and name the folder it would create inside the workspace."""
    checked = validate_url(url)
    if not isinstance(folder, str) or not folder.strip():
        tail = checked.rsplit('/', 1)[-1]
        folder = tail[:-4] if tail.casefold().endswith('.git') else tail
    target = Path(folder.strip())
    if target.is_absolute() or '..' in target.parts or not target.name:
        raise ValueError('The clone folder must be a plain name inside the task workspace.')
    return {'url': checked, 'folder': str(target)}


def _run_git(trailing_arguments, cancel_event=None):
    command = [git_executable(), 'clone', '--depth', '1', '--single-branch', *trailing_arguments]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, errors='replace',
                                   timeout=MAX_CLONE_SECONDS, shell=False)
    except subprocess.TimeoutExpired:
        raise ValueError(f'The clone did not finish within {MAX_CLONE_SECONDS} seconds and the unfinished '
                         'folder was removed, so it can be tried again.') from None
    except OSError as error:
        raise ValueError('Git could not be started: ' + str(error)[:200]) from None
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or '').strip().replace('\n', ' ')[-400:]
        raise ValueError(f'Git reported a problem, so nothing was set up: {detail}')
    if cancel_event is not None and cancel_event.is_set():
        raise ValueError('Cancelled while the clone was running.')
    return completed


def survey(target):
    """Count files and list the top level so the next step can see what the repository holds."""
    if not target.is_dir():
        raise ValueError('Git reported success but the clone folder is missing.')
    top_level = [entry.name + ('/' if entry.is_dir() else '')
                 for entry in sorted(target.iterdir(), key=lambda item: item.name.casefold())]
    files = 0
    for path in target.rglob('*'):
        if '.git' in path.parts or not path.is_file():
            continue
        files += 1
        if files >= MAX_REPORTED_FILES:
            break
    return files, top_level[:40]


def partial_clone(target):
    """True for a folder holding nothing but a .git directory — a clone that never checked files out.

    A killed clone (the usual cause is a step timeout during a large download) leaves exactly this,
    and it makes every later clone into the same folder fail with "destination already exists".
    """
    try:
        entries = list(target.iterdir())
    except OSError:
        return False
    return len(entries) == 1 and entries[0].is_dir() and entries[0].name.casefold() == '.git'


def repository_key(url):
    """The compared form of a clone URL: https-only, no trailing slash, and '.git' optional.

    GitHub answers both spellings with either form in the folder's own config, so a match has to
    ignore the suffix instead of comparing the two strings a task happens to have written down."""
    try:
        checked = validate_url(url)
    except ValueError:
        return ''
    return checked[:-4] if checked.casefold().endswith('.git') else checked


def already_cloned(target, url):
    """True when the folder is a working copy of exactly this repository.

    A setup task resumed after a restart re-proposes its clone, and the repository is already on disk
    from the first pass. Failing the step reads as missing work, so the planner hunts for another
    folder name and downloads a second copy of the same hundred megabytes.
    """
    if not target.is_dir():
        return False
    try:
        completed = subprocess.run([git_executable(), '-C', str(target), 'remote', 'get-url', 'origin'],
                                   capture_output=True, text=True, errors='replace', timeout=30, shell=False)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return False
    if completed.returncode != 0:
        return False
    wanted = repository_key(url)
    return bool(wanted) and repository_key(completed.stdout.strip()) == wanted


def clone(url, target, cancel_event=None):
    """Clone shallowly into `target`, which must be absent or a dead partial clone, and report what landed."""
    checked = validate_url(url)
    destination = Path(target)
    replacing = False
    if destination.exists() and any(destination.iterdir()):
        if not partial_clone(destination):
            raise ValueError(f'{destination} already holds files. Choose another folder or clear it first.')
        replacing = True
    if cancel_event is not None and cancel_event.is_set():
        raise ValueError('Cancelled before the clone started.')
    if replacing:
        shutil.rmtree(destination)
    try:
        _run_git(['--', checked, str(destination)], cancel_event=cancel_event)
    except Exception:
        # Leave no debris behind, or the retry would be refused by the folder it just corrupted.
        if destination.exists() and partial_clone(destination):
            shutil.rmtree(destination, ignore_errors=True)
        raise
    files, top_level = survey(destination)
    return {'ok': True, 'url': checked, 'folder': str(destination), 'files': files, 'top_level': top_level,
            'replaced_partial_clone': replacing,
            'message': (f'Removed the unfinished clone that was sitting in {destination.name} and ' if replacing else 'Cloned ')
                       + f'{checked} into {destination.name} ({files} files). Nothing from it has been run.'}
