"""Native Unicode clipboard for the Windows desktop bridge."""
import ctypes
import sys
import time

def copy_text(text):
    if not isinstance(text,str) or len(text)>4096 or '\x00' in text:
        raise ValueError('Clipboard text must be at most 4096 characters.')
    if sys.platform!='win32':
        raise RuntimeError('Use the browser clipboard or select the text and copy it.')
    from ctypes import wintypes
    user=ctypes.WinDLL('user32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    user.OpenClipboard.argtypes=[wintypes.HWND];user.OpenClipboard.restype=wintypes.BOOL
    user.EmptyClipboard.restype=wintypes.BOOL
    user.SetClipboardData.argtypes=[wintypes.UINT,wintypes.HANDLE];user.SetClipboardData.restype=wintypes.HANDLE
    user.CloseClipboard.restype=wintypes.BOOL
    user.CreateWindowExW.argtypes=[wintypes.DWORD,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.DWORD,
        ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.HWND,wintypes.HMENU,wintypes.HINSTANCE,ctypes.c_void_p]
    user.CreateWindowExW.restype=wintypes.HWND
    user.DestroyWindow.argtypes=[wintypes.HWND]
    kernel.GlobalAlloc.argtypes=[wintypes.UINT,ctypes.c_size_t];kernel.GlobalAlloc.restype=wintypes.HGLOBAL
    kernel.GlobalLock.argtypes=[wintypes.HGLOBAL];kernel.GlobalLock.restype=ctypes.c_void_p
    kernel.GlobalUnlock.argtypes=[wintypes.HGLOBAL];kernel.GlobalFree.argtypes=[wintypes.HGLOBAL]
    raw=(text+'\0').encode('utf-16-le');handle=kernel.GlobalAlloc(0x0002,len(raw))
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    # Clipboard ownership needs a real HWND; a message-only window stays
    # invisible and belongs to this API thread.
    owner=user.CreateWindowExW(0,'STATIC','Sakura clipboard',0,0,0,0,0,wintypes.HWND(-3),None,None,None)
    if not owner:
        kernel.GlobalFree(handle);raise ctypes.WinError(ctypes.get_last_error())
    transferred=False;opened=False
    try:
        pointer=kernel.GlobalLock(handle)
        if not pointer:raise ctypes.WinError(ctypes.get_last_error())
        ctypes.memmove(pointer,raw,len(raw));kernel.GlobalUnlock(handle)
        for _ in range(10):
            if user.OpenClipboard(owner):opened=True;break
            time.sleep(.02)
        if not opened:raise RuntimeError('Clipboard is busy. Try Copy again.')
        if not user.EmptyClipboard() or not user.SetClipboardData(13,handle):
            raise ctypes.WinError(ctypes.get_last_error())
        transferred=True
        return {'copied':True}
    finally:
        if opened:user.CloseClipboard()
        if not transferred:kernel.GlobalFree(handle)
        user.DestroyWindow(owner)


def read_text():
    """Read plain Unicode text only after an explicit request; never watch clipboard."""
    if sys.platform!='win32':raise RuntimeError('PC clipboard reading currently supports Windows only.')
    from ctypes import wintypes as w
    user=ctypes.WinDLL('user32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    user.OpenClipboard.argtypes=[w.HWND];user.OpenClipboard.restype=w.BOOL
    user.GetClipboardData.argtypes=[w.UINT];user.GetClipboardData.restype=w.HANDLE
    user.CloseClipboard.restype=w.BOOL
    kernel.GlobalLock.argtypes=[w.HGLOBAL];kernel.GlobalLock.restype=ctypes.c_void_p
    kernel.GlobalUnlock.argtypes=[w.HGLOBAL];kernel.GlobalSize.argtypes=[w.HGLOBAL];kernel.GlobalSize.restype=ctypes.c_size_t
    opened=False
    try:
        for _ in range(10):
            if user.OpenClipboard(None):opened=True;break
            time.sleep(.02)
        if not opened:raise RuntimeError('Clipboard is busy. Try again.')
        handle=user.GetClipboardData(13)
        if not handle:return ''
        size=kernel.GlobalSize(handle)
        if size>8194:raise ValueError('Clipboard text exceeds the 4096 character limit.')
        pointer=kernel.GlobalLock(handle)
        if not pointer:raise ctypes.WinError(ctypes.get_last_error())
        try:
            raw=ctypes.string_at(pointer,size)
            text=raw.decode('utf-16-le',errors='strict').split('\0',1)[0]
            if len(text)>4096:raise ValueError('Clipboard text exceeds the 4096 character limit.')
            return text
        finally:kernel.GlobalUnlock(handle)
    finally:
        if opened:user.CloseClipboard()
