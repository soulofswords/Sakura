"""Bounded process inspection and guarded termination for reviewed local actions."""
import os

import psutil


_SYSTEM_NAMES = {
    'system', 'registry', 'secure system', 'memory compression', 'idle',
    'smss.exe', 'csrss.exe', 'wininit.exe', 'services.exe', 'lsass.exe',
    'winlogon.exe', 'svchost.exe', 'fontdrvhost.exe', 'dwm.exe',
}


def list_processes(limit=100):
    """Return bounded PID/name/status rows without command lines or environment data."""
    try:
        limit = max(1, min(200, int(limit)))
    except (TypeError, ValueError):
        limit = 100
    rows = []
    for process in psutil.process_iter(('pid', 'name', 'status')):
        try:
            pid = int(process.info.get('pid'))
            name = str(process.info.get('name') or '(unnamed)')[:160]
            status = str(process.info.get('status') or '')[:40]
            if pid > 0:
                rows.append({'pid': pid, 'name': name, 'status': status})
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError, ValueError):
            continue
    rows.sort(key=lambda item: (item['name'].casefold(), item['pid']))
    total = len(rows)
    return {'ok': True, 'processes': rows[:limit], 'count': total, 'limited': total > limit}


def _protected_pids():
    protected = {0, 4, os.getpid()}
    try:
        protected.update(parent.pid for parent in psutil.Process().parents())
    except (psutil.Error, OSError):
        pass
    return protected


def inspect_target(pid):
    """Resolve a PID to a stable identity and refuse OS/other-user/Sakura processes."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        raise ValueError('Choose a numeric process ID from the current process list.') from None
    if pid <= 4 or pid in _protected_pids():
        raise ValueError('Sakura and protected Windows processes cannot be terminated.')
    try:
        target = psutil.Process(pid)
        with target.oneshot():
            name = str(target.name() or '(unnamed)')[:160]
            username = str(target.username() or '')
            created = float(target.create_time())
        current_user = str(psutil.Process().username() or '')
    except psutil.NoSuchProcess:
        raise ValueError('That process no longer exists. Refresh the process list.') from None
    except (psutil.AccessDenied, OSError):
        raise ValueError('Windows did not allow Sakura to inspect that process, so it will not be terminated.') from None
    if name.casefold() in _SYSTEM_NAMES:
        raise ValueError('Protected Windows processes cannot be terminated.')
    if not username or not current_user or username.casefold() != current_user.casefold():
        raise ValueError('Only a process owned by the current Windows user can be terminated.')
    return {'pid': pid, 'name': name, 'username': username, 'created': created}


def terminate(pid, expected=None):
    """Request graceful termination after re-checking the identity approved by the user."""
    identity = inspect_target(pid)
    if expected is not None:
        checked = {key: identity[key] for key in ('pid', 'name', 'username', 'created')}
        wanted = {key: expected.get(key) for key in checked}
        if checked != wanted:
            raise ValueError('The process at that PID changed after review. Refresh the list and approve it again.')
    try:
        process = psutil.Process(identity['pid'])
        # Bind this exact psutil handle to the identity just inspected. A PID may
        # be reused between inspection and acquiring the termination handle.
        if process.create_time() != identity['created']:
            raise ValueError('The process at that PID changed before termination. Refresh the list and approve it again.')
        process.terminate()
        try:
            process.wait(timeout=3)
            stopped = True
        except psutil.TimeoutExpired:
            stopped = False
    except psutil.NoSuchProcess:
        stopped = True
    except (psutil.AccessDenied, OSError):
        raise ValueError('Windows refused the termination request. Nothing else was attempted.') from None
    return {'ok': stopped, 'pid': identity['pid'], 'name': identity['name'], 'stopped': stopped,
            'message': (f"Terminated {identity['name']} ({identity['pid']})." if stopped else
                        f"Asked {identity['name']} ({identity['pid']}) to close, but it is still running.")}
