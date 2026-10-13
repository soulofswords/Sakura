"""Lightweight Windows foreground-game heuristics; no screenshots required."""
import os
import time
import sys

NON_GAMES = {'chrome.exe', 'msedge.exe', 'firefox.exe', 'explorer.exe', 'vlc.exe',
             'obs64.exe', 'discord.exe', 'steam.exe', 'code.exe', 'python.exe', 'pythonw.exe',
             'powershell.exe', 'pwsh.exe', 'cmd.exe', 'windowsterminal.exe',
             'epicgameslauncher.exe', 'epicwebhelper.exe', 'steamwebhelper.exe',
             'wallpaper64.exe', 'wallpaper32.exe', 'blender.exe', 'vtube studio.exe', 'vroidstudio.exe'}


def classify_game(executable, fullscreen=False):
    path = executable.lower().replace('\\', '/')
    name = path.rsplit('/', 1)[-1]
    if not name or name in NON_GAMES:
        return False
    return any(marker in path for marker in ('/steamapps/common/', '/epic games/',
        '/riot games/', '/games/', '/gog galaxy/games/', '/xboxgames/')) or fullscreen


def foreground_game():
    if sys.platform == 'darwin':
        from macos_support import foreground_game as mac_game
        return mac_game()
    if os.name != 'nt':
        return {'detected': False, 'name': ''}
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL('user32')
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    hwnd = user32.GetForegroundWindow()
    owner = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
    if not owner.value or owner.value == os.getpid():
        return {'detected': False, 'name': ''}
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, owner.value)
    if not handle:
        return {'detected': False, 'name': ''}
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(buffer))
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
            return {'detected': False, 'name': ''}
        executable = buffer.value
    finally:
        kernel.CloseHandle(handle)
    rect = wintypes.RECT()
    fullscreen = False
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        # Borderless/fullscreen windows typically cover a monitor exactly.
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = wintypes.HANDLE
        class MonitorInfo(ctypes.Structure):
            _fields_ = [('size', wintypes.DWORD), ('monitor', wintypes.RECT), ('work', wintypes.RECT), ('flags', wintypes.DWORD)]
        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
        info = MonitorInfo()
        info.size = ctypes.sizeof(info)
        if user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(info)):
            fullscreen = all(abs(getattr(rect, side) - getattr(info.monitor, side)) <= 2 for side in ('left', 'top', 'right', 'bottom'))
    return {'detected': classify_game(executable, fullscreen), 'name': os.path.basename(executable), 'pid': owner.value}


def process_running(pid):
    if sys.platform == 'darwin' and pid:
        try:
            os.kill(int(pid), 0)
            return True
        except (OSError, ValueError):
            return False
    if os.name != 'nt' or not pid:
        return False
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32')
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
    finally:
        kernel.CloseHandle(handle)


_game_names = set()
_game_names_checked = 0

def installed_game_process_names():
    global _game_names, _game_names_checked
    if time.monotonic() - _game_names_checked < 60:
        return _game_names
    from pathlib import Path
    from steam_commands import installed_games
    names = set()
    for game in installed_games():
        folder = game.get('install_dir')
        if not folder:
            continue
        root = Path(folder)
        for pattern in ('*.exe', '*/Binaries/Win64/*.exe', 'Binaries/Win64/*.exe'):
            for executable in root.glob(pattern):
                name = executable.name.lower()
                if name not in NON_GAMES and not any(word in name for word in ('crash', 'setup', 'unins', 'redist', 'launcher', 'anticheat', 'start_protected', 'runfallguys')):
                    names.add(name)
    _game_names, _game_names_checked = names, time.monotonic()
    return names


def process_inventory():
    """Toolhelp names remain readable when anti-cheat denies opening a process."""
    if os.name != 'nt':
        return []
    import ctypes
    from ctypes import wintypes
    class ProcessEntry(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('usage', wintypes.DWORD), ('pid', wintypes.DWORD),
                    ('heap', ctypes.c_size_t), ('module', wintypes.DWORD), ('threads', wintypes.DWORD),
                    ('parent', wintypes.DWORD), ('priority', wintypes.LONG), ('flags', wintypes.DWORD),
                    ('exe', wintypes.WCHAR * 260)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        return []
    result = []
    try:
        entry = ProcessEntry(); entry.size = ctypes.sizeof(entry)
        success = kernel.Process32FirstW(handle, ctypes.byref(entry))
        while success:
            result.append({'pid': entry.pid, 'name': entry.exe})
            success = kernel.Process32NextW(handle, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(handle)
    return result


def running_library_game():
    names = installed_game_process_names()
    for process in process_inventory():
        if process['name'].lower() in names:
            foreground = False
            if os.name == 'nt':
                import ctypes
                from ctypes import wintypes
                user = ctypes.WinDLL('user32')
                user.GetForegroundWindow.restype = wintypes.HWND
                user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
                owner = wintypes.DWORD()
                user.GetWindowThreadProcessId(user.GetForegroundWindow(), ctypes.byref(owner))
                foreground = owner.value == process['pid']
            return {**process, 'detected': True, 'foreground': foreground}
    return {'detected': False, 'name': '', 'foreground': False}


def game_session(previous=None):
    current = foreground_game()
    if current['detected']:
        return {**current, 'foreground': True}
    if previous and process_running(previous.get('pid')):
        return {**previous, 'detected': True, 'foreground': False}
    return running_library_game()
