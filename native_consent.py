"""OS confirmation for grants which a loopback bearer must not authorize alone."""
import json
import sys
import threading

_prompt_lock=threading.Lock()


def confirm(title,details):
    if sys.platform!='win32':
        raise PermissionError('Native approval is required; this platform has no configured approval window.')
    import ctypes
    from ctypes import wintypes
    text=json.dumps(details,ensure_ascii=False,indent=2,default=str)
    if len(text)>18000:
        raise ValueError('The approval preview is too large for the native review window. Split this action into smaller steps.')
    with _prompt_lock:
        show=ctypes.WinDLL('user32',use_last_error=True).MessageBoxW
        show.argtypes=[wintypes.HWND,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.UINT]
        show.restype=ctypes.c_int
        # Yes/No, default No, foreground, warning icon. No text from the model
        # can choose the result; only Windows' dialog result permits the grant.
        return show(None,'Review this Sakura request:\n\n'+text+'\n\nAllow this exact request?',
                    'Sakura approval — '+title,0x4|0x100|0x30|0x10000)==6
