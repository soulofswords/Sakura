"""Windows DPAPI or macOS Keychain storage for the Gemini API key."""
import ctypes
import sys
from ctypes import wintypes
from config import BASE_DIR

KEY_FILE = BASE_DIR / ".gemini-key.bin"

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
