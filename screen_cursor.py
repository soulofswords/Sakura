import sys


_user32 = None


def _windows_position():
    import ctypes
    from ctypes import wintypes

    global _user32
    if _user32 is None:
        _user32 = ctypes.WinDLL('user32')
        _user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        _user32.GetCursorPos.restype = wintypes.BOOL
    user32 = _user32
    point = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        return None
    left, top = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    width, height = max(1, user32.GetSystemMetrics(78)), max(1, user32.GetSystemMetrics(79))
    return {'x': (point.x - left) / width * 2 - 1, 'y': (point.y - top) / height * 2 - 1}


def position():
    """Screen cursor in normalized -1..1 coordinates, independent of window focus."""
    if sys.platform == 'darwin':
        from macos_support import cursor_position
        return cursor_position()
    if sys.platform == 'win32':
        return _windows_position()
    return None
