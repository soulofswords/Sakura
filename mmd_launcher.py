"""Launch a user-selected complete MikuMikuDance installation."""
import os
from pathlib import Path
import subprocess
import struct
import time


def _drop_payload(file):
    # DROPFILES followed by one double-NUL-terminated UTF-16 filename.
    return struct.pack('<IiiII',20,0,0,0,1)+(str(file)+'\0\0').encode('utf-16-le')


def _send_model_drop(window,file):
    """Deliver the standard shell file-drop message; receiver owns HDROP."""
    import ctypes
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    user=ctypes.WinDLL('user32',use_last_error=True)
    kernel.GlobalAlloc.argtypes=[wintypes.UINT,ctypes.c_size_t];kernel.GlobalAlloc.restype=ctypes.c_void_p
    kernel.GlobalLock.argtypes=[ctypes.c_void_p];kernel.GlobalLock.restype=ctypes.c_void_p
    kernel.GlobalUnlock.argtypes=[ctypes.c_void_p];kernel.GlobalUnlock.restype=wintypes.BOOL
    kernel.GlobalFree.argtypes=[ctypes.c_void_p];kernel.GlobalFree.restype=ctypes.c_void_p
    user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM];user.PostMessageW.restype=wintypes.BOOL
    payload=_drop_payload(file);handle=kernel.GlobalAlloc(0x42,len(payload))
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    transferred=False
    try:
        pointer=kernel.GlobalLock(handle)
        if not pointer:raise ctypes.WinError(ctypes.get_last_error())
        try:ctypes.memmove(pointer,payload,len(payload))
        finally:kernel.GlobalUnlock(handle)
        if not user.PostMessageW(window,0x233,handle,0):raise ctypes.WinError(ctypes.get_last_error())
        transferred=True
    finally:
        if not transferred:kernel.GlobalFree(handle)


def _model_window(process,timeout=25):
    """Only target the newly launched PID, never a user's existing MMD scene."""
    import ctypes
    from ctypes import wintypes
    user=ctypes.WinDLL('user32',use_last_error=True)
    callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    user.EnumWindows.argtypes=[callback,wintypes.LPARAM];user.EnumWindows.restype=wintypes.BOOL
    user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int];user.GetWindowLongW.restype=ctypes.c_long
    user.IsWindowVisible.argtypes=[wintypes.HWND];user.IsWindowVisible.restype=wintypes.BOOL
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if process.poll() is not None:raise RuntimeError('MikuMikuDance exited before it could receive the selected model.')
        found=[]
        @callback
        def inspect(window,_):
            pid=wintypes.DWORD();user.GetWindowThreadProcessId(window,ctypes.byref(pid))
            if pid.value==process.pid and user.IsWindowVisible(window) and user.GetWindowLongW(window,-20)&0x10:
                found.append(window)
            return True
        user.EnumWindows(inspect,0)
        if len(found)==1:return found[0]
        if len(found)>1:raise RuntimeError('MMD exposed several model-drop windows. The model was not sent to an ambiguous target.')
        time.sleep(.1)
    raise RuntimeError('MMD did not become ready to receive the selected PMX. Close any MMD startup/error dialog and try again.')


def find_mmd(value):
    if not isinstance(value,str) or not value.strip():return None
    path=Path(value).expanduser()
    if path.is_dir():path=path/'MikuMikuDance.exe'
    if path.name.casefold()!='mikumikudance.exe' or not path.is_file():return None
    if not (path.parent/'Data').is_dir():return None
    return path.resolve()


def open_mmd(value,relative_path):
    from pmx_editor import model_file
    file=model_file(relative_path)
    if os.name!='nt':raise RuntimeError('MikuMikuDance is available on Windows.')
    path=find_mmd(value)
    if path is None:raise ValueError('Choose MikuMikuDance.exe from its complete installation folder.')
    process=subprocess.Popen([str(path)],cwd=str(path.parent),creationflags=subprocess.CREATE_NO_WINDOW)
    window=_model_window(process)
    _send_model_drop(window,file)
    return {'opened':True,'model':relative_path,'import_requested':True}
