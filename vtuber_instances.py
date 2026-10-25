"""OS-owned VTuber slots: a crash releases its slot automatically."""
import atexit
import ctypes
import hashlib
import os
from pathlib import Path
import subprocess
import sys

MAX_INSTANCES = 3

def instance_index():
    try:
        return max(1, min(MAX_INSTANCES, int(os.environ.get('SAKURA_INSTANCE_INDEX', '1'))))
    except ValueError:
        return 1

def claim_instance(root):
    if sys.platform != 'win32':
        raise RuntimeError('Multiple VTuber instances are currently supported on Windows.')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    identity = hashlib.sha256(str(Path(root).resolve()).casefold().encode()).hexdigest()[:16]
    for slot in range(1, MAX_INSTANCES + 1):
        ctypes.set_last_error(0)
        handle = kernel.CreateMutexW(None, False, f'Local\\SakuraVTuber_{identity}_{slot}')
        error = ctypes.get_last_error()
        if not handle:
            raise OSError(error, 'Could not reserve a VTuber instance slot.')
        if error != 183:
            atexit.register(kernel.CloseHandle, handle)
            os.environ['SAKURA_INSTANCE_INDEX'] = str(slot)
            return slot
        kernel.CloseHandle(handle)
    raise RuntimeError('Three Sakura VTuber instances are already open. Close one before opening another.')

def spawn_instance(root):
    environment = os.environ.copy()
    environment.pop('SAKURA_INSTANCE_INDEX', None)
    environment['SAKURA_START_MODE'] = 'vtuber'
    environment['SAKURA_VTUBER_INSTANCE'] = '1'
    environment['SAKURA_UPLOAD_UI'] = '1'
    return subprocess.Popen([sys.executable, '-u', str(Path(root) / 'desktop.py')],
                            cwd=root, env=environment,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
