"""Sakura's separate DirectShow camera and private frame transport."""
import ctypes
from pathlib import Path
import sys
import time

DRIVER_DLL = Path(__file__).resolve().parent/'native'/'sakura-camera'/'bin'/'x64'/'sakura-camera64.dll'
CAMERA_NAME = 'Sakura Virtual Camera'
CAMERA_CLSID = '{5F4A34D7-C3B9-4E6D-9A12-8A4D3C6E7201}'

def _regsvr32(action, arguments, workdir):
    import os
    executable = Path(os.environ['WINDIR'])/'System32'/'regsvr32.exe'
    shell = ctypes.windll.shell32.ShellExecuteW
    shell.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int]
    shell.restype = ctypes.c_void_p
    result = shell(None, 'runas', str(executable), arguments, str(workdir), 0)
    if not result or result <= 32:
        raise RuntimeError('Windows '+action+' was cancelled or could not start.')

def _registered_dll_path():
    """Path Windows currently resolves our camera CLSID to, or None."""
    if sys.platform != 'win32':
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, 'CLSID\\'+CAMERA_CLSID+'\\InprocServer32') as key:
            path = Path(winreg.QueryValueEx(key, '')[0])
    except OSError:
        return None
    return path if path.is_file() else None

def install_driver():
    if sys.platform != 'win32':
        raise RuntimeError('Sakura Virtual Camera is available on Windows.')
    if not DRIVER_DLL.is_file():
        raise RuntimeError('This build does not include the Sakura camera driver yet.')
    if driver_installed():
        return {'installed': True, 'device': CAMERA_NAME}
    _regsvr32('camera installation', '/s "'+str(DRIVER_DLL)+'"', DRIVER_DLL.parent)
    for _ in range(120):
        if driver_installed():
            return {'installed': True, 'device': CAMERA_NAME}
        time.sleep(.25)
    raise RuntimeError('Camera registration is not complete. Approve the Windows installation prompt, then try again.')

def uninstall_driver():
    if sys.platform != 'win32':
        raise RuntimeError('Sakura Virtual Camera is available on Windows.')
    registered = _registered_dll_path()
    if registered is None:
        return {'installed': False, 'device': CAMERA_NAME}
    _regsvr32('camera removal', '/s /u "'+str(registered)+'"', registered.parent)
    for _ in range(120):
        if not driver_installed():
            return {'installed': False, 'device': CAMERA_NAME}
        time.sleep(.25)
    raise RuntimeError('Windows has not finished removing the camera. Close your video apps, then try again.')

def driver_installed():
    return _registered_dll_path() is not None

class NativeCamera:
    def __init__(self, width=1280, height=720, fps=30):
        if not driver_installed():
            raise RuntimeError('Install Sakura Virtual Camera using native/sakura-camera/install-camera.ps1, then reopen your video app.')
        path = Path(__file__).resolve().parent/'native'/'sakura-camera'/'bin'/'x64'/'sakura-camera-bridge64.dll'
        self.dll = ctypes.CDLL(str(path))
        self.dll.sakura_camera_open.argtypes = [ctypes.c_uint32]*3
        self.dll.sakura_camera_open.restype = ctypes.c_int
        self.dll.sakura_camera_send.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.dll.sakura_camera_send.restype = ctypes.c_int
        self.dll.sakura_camera_close.argtypes = []
        self.dll.sakura_camera_close.restype = None
        if not self.dll.sakura_camera_open(width, height, fps):
            raise RuntimeError('Sakura Virtual Camera is already being sent by another Sakura instance.')
        self.device = CAMERA_NAME

    def send(self, rgb):
        if not rgb.flags.c_contiguous or rgb.dtype.name != 'uint8':
            raise ValueError('Camera frames must be contiguous RGB bytes.')
        if not self.dll.sakura_camera_send(rgb.ctypes.data, rgb.nbytes):
            raise RuntimeError('Sakura camera rejected the frame dimensions.')

    def close(self):
        self.dll.sakura_camera_close()
