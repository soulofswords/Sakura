"""Windows DPAPI or macOS Keychain storage for the Gemini API key."""
import ctypes
import sys
import json
import hashlib
import threading
from ctypes import wintypes
from config import BASE_DIR

KEY_FILE = BASE_DIR / ".gemini-key.bin"
CLOUD_KEY_FILE = BASE_DIR / '.cloud-keys.bin'
_cloud_lock = threading.RLock()

def _cloud_slot(provider,endpoint=''):
    return provider+(':'+hashlib.sha256(endpoint.rstrip('/').encode()).hexdigest() if provider=='compatible' else '')

def get_cloud_key(provider,endpoint=''):
    slot=_cloud_slot(provider,endpoint)
    if sys.platform=='darwin':return _mac_keyring().get_password('Sakura Companion',slot) or ''
    with _cloud_lock:
        if not CLOUD_KEY_FILE.exists():return ''
        return json.loads(_crypt(CLOUD_KEY_FILE.read_bytes(),decrypt=True).decode('utf-8')).get(slot,'')

def set_cloud_key(provider,key,endpoint=''):
    slot=_cloud_slot(provider,endpoint)
    if sys.platform=='darwin':
        store=_mac_keyring()
        if key:store.set_password('Sakura Companion',slot,key)
        elif store.get_password('Sakura Companion',slot):store.delete_password('Sakura Companion',slot)
        return
    with _cloud_lock:
        data=json.loads(_crypt(CLOUD_KEY_FILE.read_bytes(),decrypt=True).decode('utf-8')) if CLOUD_KEY_FILE.exists() else {}
        if key:data[slot]=key
        else:data.pop(slot,None)
        temporary=CLOUD_KEY_FILE.with_suffix('.tmp')
        temporary.write_bytes(_crypt(json.dumps(data).encode('utf-8')));temporary.replace(CLOUD_KEY_FILE)

def _mac_keyring():
    # Explicit Apple Keychain backend, never a plaintext fallback backend.
    from keyring.backends.macOS import Keyring
    return Keyring()

class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

def _crypt(data, decrypt=False):
    buffer = ctypes.create_string_buffer(data)
    incoming = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    outgoing = Blob()
    crypto = ctypes.WinDLL("crypt32", use_last_error=True)
    function = crypto.CryptUnprotectData if decrypt else crypto.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
        raise OSError("Windows could not protect or read the saved Gemini key.")
    try:
        return ctypes.string_at(outgoing.data, outgoing.size)
    finally:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        kernel.LocalFree(ctypes.cast(outgoing.data, ctypes.c_void_p))

def get_gemini_key():
    if sys.platform == 'darwin':
        try:
            return _mac_keyring().get_password('Sakura Companion', 'gemini-api-key') or ''
        except Exception as exc:
            raise OSError('macOS Keychain could not read the Gemini key.') from exc
    if not KEY_FILE.exists(): return ""
    return _crypt(KEY_FILE.read_bytes(), decrypt=True).decode("utf-8")

def set_gemini_key(key):
    if sys.platform == 'darwin':
        try:
            keyring = _mac_keyring()
            if key:
                keyring.set_password('Sakura Companion', 'gemini-api-key', key)
            elif keyring.get_password('Sakura Companion', 'gemini-api-key') is not None:
                keyring.delete_password('Sakura Companion', 'gemini-api-key')
        except Exception as exc:
            raise OSError('macOS Keychain could not save or remove the Gemini key.') from exc
        return
    if not key:
        KEY_FILE.unlink(missing_ok=True)
        return
    temporary = KEY_FILE.with_suffix(".tmp")
    temporary.write_bytes(_crypt(key.encode("utf-8")))
    temporary.replace(KEY_FILE)
