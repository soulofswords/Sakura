"""Windows taskbar identity for a GUI hosted by the Store Python runtime."""
import ctypes
import uuid
from ctypes import wintypes

class GUID(ctypes.Structure):
    _fields_ = [('data', ctypes.c_ubyte * 16)]
    def __init__(self, value):
        super().__init__()
        self.data[:] = uuid.UUID(value).bytes_le

class PROPERTYKEY(ctypes.Structure):
    _fields_ = [('fmtid', GUID), ('pid', wintypes.DWORD)]

class PROPVARIANT(ctypes.Structure):
    _fields_ = [('vt', ctypes.c_ushort), ('reserved', ctypes.c_ushort * 3),
                ('value', ctypes.c_void_p), ('padding', ctypes.c_void_p)]

def set_taskbar_identity(hwnd, app_id, launcher, icon):
    shell = ctypes.WinDLL('shell32')
    get_store = shell.SHGetPropertyStoreForWindow
    get_store.argtypes = [wintypes.HWND, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
    get_store.restype = ctypes.c_long
    store = ctypes.c_void_p()
    iid = GUID('886d8eeb-8cf2-4446-8d02-cdba1dbdcf99')
    result = get_store(hwnd, ctypes.byref(iid), ctypes.byref(store))
    if result < 0:
        raise OSError(f'Could not obtain taskbar property store: {result}')
    table = ctypes.cast(store, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    set_value = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
        ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT))(table[6])
    commit = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(table[7])
    release = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(table[2])
    try:
        for pid, text in [(5, app_id), (2, f'"{launcher}"'), (3, f'{icon},0'),
                          (4, 'Sakura Companion')]:
            key = PROPERTYKEY(GUID('9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3'), pid)
            buffer = ctypes.create_unicode_buffer(text)
            value = PROPVARIANT()
            value.vt = 31
            value.value = ctypes.cast(buffer, ctypes.c_void_p)
            result = set_value(store, ctypes.byref(key), ctypes.byref(value))
            if result < 0:
                raise OSError(f'Could not set taskbar identity: {result}')
        if commit(store) < 0:
            raise OSError('Could not commit taskbar identity')
    finally:
        release(store)
