"""Native input transparency without recreating the Qt renderer."""
import ctypes

def restore_window(hwnd):
    """Clear Windows' maximize placement without hiding a transparent window."""
    from ctypes import wintypes
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.IsZoomed.argtypes = [wintypes.HWND]
    user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    if user.IsZoomed(hwnd):
        user.ShowWindow(hwnd, 9)  # SW_RESTORE; Qt can miss this on layered windows.

def set_topmost(hwnd, enabled, user=None):
    """Change z-order without recreating Qt's transparent WebEngine surface."""
    if user is None:
        user = ctypes.WinDLL('user32', use_last_error=True)
        from ctypes import wintypes
        user.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    if bool(user.GetWindowLongPtrW(hwnd, -20) & 0x8) == bool(enabled):
        return True
    # No frame change, resize, activation, or hide/show: preserve the GPU surface.
    if not user.SetWindowPos(hwnd, -1 if enabled else -2, 0, 0, 0, 0, 0x1 | 0x2 | 0x10):
        return False
    return bool(user.GetWindowLongPtrW(hwnd, -20) & 0x8) == bool(enabled)

def set_click_through(hwnd, enabled, user=None):
    if user is None:
        user = ctypes.WinDLL('user32', use_last_error=True)
        from ctypes import wintypes
        user.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        user.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        user.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    style = user.GetWindowLongPtrW(hwnd, -20)
    # Layered + transparent makes the whole overlay pass input to windows below.
    # Keep all existing renderer/topmost bits, and only remove input transparency.
    updated = (style | 0x80000 | 0x20) if enabled else (style & ~0x20)
    if updated == style:
        return True
    user.SetWindowLongPtrW(hwnd, -20, updated)
    user.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)
    return bool(user.GetWindowLongPtrW(hwnd, -20) & 0x20) == bool(enabled)
