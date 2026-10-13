"""Read-only native diagnostics for Sakura and Valorant window visibility."""
import ctypes
from ctypes import wintypes
user = ctypes.WinDLL('user32')
callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user.IsWindowVisible.argtypes = [wintypes.HWND]
user.IsIconic.argtypes = [wintypes.HWND]
user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user.GetWindowDisplayAffinity.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]

@callback_type
def visit(hwnd, _):
    title = ctypes.create_unicode_buffer(512)
    user.GetWindowTextW(hwnd, title, len(title))
    if title.value.strip() in {'Sakura Desktop Companion', 'VALORANT'}:
        rect = wintypes.RECT()
        user.GetWindowRect(hwnd, ctypes.byref(rect))
        affinity = wintypes.DWORD()
        user.GetWindowDisplayAffinity(hwnd, ctypes.byref(affinity))
        print({'title': title.value, 'visible': bool(user.IsWindowVisible(hwnd)),
               'minimized': bool(user.IsIconic(hwnd)), 'topmost': bool(user.GetWindowLongPtrW(hwnd, -20) & 8),
               'capture_affinity': affinity.value, 'rect': [rect.left, rect.top, rect.right, rect.bottom]}, flush=True)
    return True

user.EnumWindows(visit, 0)
