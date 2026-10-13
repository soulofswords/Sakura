"""
🌸 Sakura — Transparent Floating Desktop Companion
Run:  python desktop.py
Launches Sakura as a frameless, transparent floating desktop widget!
"""
import sys
import time
import threading
import os
import faulthandler
from pathlib import Path
from product import DISPLAY_NAME, LAUNCHER_NAME, EDITION
APP_DISPLAY_NAME = DISPLAY_NAME
APP_USER_MODEL_ID = 'Sakura.VTuber' if EDITION=='vtuber' else 'Sakura.DesktopCompanion'
APP_ICON_PATH = Path(__file__).parent / 'launcher' / 'companion.ico'
from PySide6.QtCore import QCoreApplication
# Set identity before Qt creates its persistent browser profile, avoiding a
# shared default cache lock between the Companion and VTuber processes.
QCoreApplication.setApplicationName(APP_DISPLAY_NAME)
QCoreApplication.setOrganizationName('SoulOfSwords')
APP_LAUNCHER_PATH = Path(__file__).parent.parent / LAUNCHER_NAME
if not APP_LAUNCHER_PATH.is_file():
    # Owner's local edition launchers share the outer development root.
    APP_LAUNCHER_PATH = Path(__file__).parent.parent.parent / LAUNCHER_NAME
_logs_dir = Path(__file__).parent / 'logs'
_logs_dir.mkdir(parents=True, exist_ok=True)
_crash_log = open(_logs_dir / 'desktop-crash.log', 'a', encoding='utf-8')
faulthandler.enable(file=_crash_log, all_threads=True)
os.environ['QT_API'] = 'pyside6'
os.environ['SAKURA_DESKTOP'] = '1'

# Give the native window its own taskbar group before Qt creates any windows.
# Otherwise Windows groups this app under the Python interpreter's icon.
if sys.platform == 'win32':
    # Keep the transparent Qt/Chromium surface, backed by Direct3D 11.
    # ANGLE compiles the viewer's shaders for D3D; this is not SlimDX.
    _graphics_flags = os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '')
    if '--use-angle=' not in _graphics_flags:
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = (_graphics_flags + ' --use-gl=angle --use-angle=d3d11').strip()
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)

# Configure UTF-8 encoding safely on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import uvicorn
import gui_server
import webview
from app import app, get_settings
_desktop_server = None

# ── Desktop Window API ──────────────────────────────────────────
class DesktopApi:
    def __init__(self, window_holder):
        self.holder = window_holder

    def close(self):
        """Close the desktop companion window."""
        win = self.holder.get("window")
        if win:
            win.destroy()

    def open_pmx_editor(self, model_path):
        from pmx_editor import open_model
        return open_model(model_path)

    def platform_capabilities(self):
        return {'platform': sys.platform, 'pmx_editor': sys.platform == 'win32'}

    def open_nvidia_broadcast(self):
        if sys.platform!='win32':return {'error':'NVIDIA Broadcast is available on supported Windows RTX systems.'}
        import subprocess
        roots={Path(os.environ.get('ProgramFiles','C:/Program Files')),Path(os.environ.get('ProgramW6432','C:/Program Files'))}
        for root in roots:
            directory=root/'NVIDIA Corporation'/'NVIDIA Broadcast'
            for name in ['NVIDIA Broadcast.exe','NVIDIA Broadcast UI.exe','NVIDIA Broadcast/NVIDIA Broadcast.exe']:
                executable=directory/name
                if executable.is_file():
                    subprocess.Popen([str(executable)],cwd=executable.parent)
                    return {'ok':True}
        return {'error':'NVIDIA Broadcast is not installed in its usual location. Install it using the NVIDIA link or open it manually.'}

    def choose_nvidia_sdk_folder(self):
        win=self.holder.get('window')
        if not win:return None
        selected=win.create_file_dialog(webview.FileDialog.FOLDER)
        return selected[0] if selected else None

    def minimize(self):
        """Minimize the companion."""
        win = self.holder.get("window")
        if win:
            win.minimize()

    def toggle_maximize(self):
        if not self.holder.get('library_mode'):
            return self.set_library_mode(True)
        bridge = self.holder.get('resize_bridge')
        if bridge:
            bridge.maximize_request.emit()
            return True
        return False

    def start_window_resize(self, edge):
        if edge not in ('n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'):
            return False
        bridge = self.holder.get('resize_bridge')
        if not bridge:
            return False
        bridge.request.emit(edge)
        return True

    def window_bounds(self):
        win = self.holder.get('window')
        return {'width': win.width, 'height': win.height, 'x': win.x, 'y': win.y} if win else None

    def resize_companion(self, width, height, x, y):
        win = self.holder.get('window')
        if not win:
            return False
        width = max(320, min(4096, int(width)))
        height = max(400, min(4096, int(height)))
        if (win.width, win.height) != (width, height):
            win.resize(width, height)
        if (win.x, win.y) != (int(x), int(y)):
            win.move(int(x), int(y))
        return True

    def set_on_top(self, enabled: bool):
        """Toggle always-on-top mode."""
        win = self.holder.get("window")
        if win:
            win.on_top = bool(enabled) and not bool(getattr(app.state, 'tracking_only', False))
            return win.on_top
        return False

    def set_character_only(self, enabled: bool):
        """Character-only view passes mouse input through; hotkey restores controls."""
        enabled = bool(enabled)
        # Never strand a click-through window without its global recovery hotkey.
        if enabled and not getattr(self, 'hotkey_registered', False):
            return False
        self.holder['character_only'] = enabled
        bridge = self.holder.get('resize_bridge')
        if bridge:
            bridge.input_request.emit(enabled)
        return enabled

    def set_transparency_hotkey(self, value):
        from companion_hotkey import parse_hotkey
        try:
            canonical, flags, vk, mac = parse_hotkey(value)
            if sys.platform == 'darwin':
                from macos_support import start_hotkey
                replacement = start_hotkey(lambda: self.holder['window'].evaluate_js('window.toggleCompanionView?.()'), mac)
                if replacement is None: return {'ok':False,'error':'Global shortcut could not be enabled. Check macOS permissions.'}
                previous = self.holder.get('mac_hotkey')
                self.holder['mac_hotkey'] = replacement
                if previous: previous.stop()
                self.hotkey_registered = True
                return {'ok':True,'hotkey':canonical}
            if sys.platform != 'win32': return {'ok':False,'error':'Global shortcuts are unavailable on this platform.'}
            thread_id = self.holder.get('hotkey_thread_id')
            if not thread_id: return {'ok':False,'error':'Shortcut service is not ready. Try again.'}
            request = {'shortcut':(canonical, flags, vk), 'done':threading.Event()}
            with self.holder['hotkey_update_lock']:
                self.holder['hotkey_request'] = request
                import ctypes
                if not ctypes.windll.user32.PostThreadMessageW(thread_id, 0x8001, 0, 0):
                    return {'ok':False,'error':'Shortcut service is unavailable.'}
                if not request['done'].wait(3): return {'ok':False,'error':'Shortcut update timed out.'}
                return request['result']
        except ValueError as error:
            return {'ok':False,'error':str(error)}

    def hotkey_status(self):
        return bool(getattr(self, 'hotkey_registered', False))

    def model_load_status(self, stage, elapsed):
        if stage in ('fetch', 'textures', 'shaders', 'ready', 'error'):
            print(f'  Model loading: {stage} ({float(elapsed):.2f}s)', flush=True)

    def model_frame_status(self, center, size):
        print(f'  Model bounds: center={center}, size={size}', flush=True)

    def choose_ollama_folder(self):
        win = self.holder.get('window')
        if not win:
            return None
        selected = win.create_file_dialog(webview.FileDialog.FOLDER)
        return selected[0] if selected else None

    def import_model_package(self, kind):
        from config import MODELS_DIR
        from model_import import import_package, MAX_BYTES
        if kind not in ('pmx', 'vrm', 'live2d'):
            return {'error': 'Choose PMX, VRM or Live2D.'}
        win = self.holder.get('window')
        if not win or not self.holder.get('library_mode'):
            return {'error': 'Open the model library to upload models.'}
        start = MODELS_DIR / kind
        start.mkdir(parents=True, exist_ok=True)
        try:
            selection = win.create_file_dialog(
                webview.FileDialog.OPEN if kind == 'vrm' else webview.FileDialog.FOLDER,
                directory=str(start), allow_multiple=False,
                file_types=('VRM models (*.vrm)',) if kind == 'vrm' else ())
            if not selection:
                return {'cancelled': True}
            selected = Path(selection[0]).resolve()
            paths = [selected] if kind == 'vrm' else sorted(p for p in selected.rglob('*') if p.is_file() and not p.is_symlink())
            if len(paths) > 5000 or sum(p.stat().st_size for p in paths) > MAX_BYTES:
                raise ValueError('Model packages must be under 512 MB and 5,000 files.')
            contents = [(p.name if kind == 'vrm' else p.relative_to(selected).as_posix(), p.read_bytes()) for p in paths]
            return import_package(MODELS_DIR, contents, kind)
        except Exception as error:
            return {'error': str(error)}

    def open_library(self):
        return self.set_library_mode(True)

    def set_library_mode(self, enabled):
        enabled = bool(enabled)
        if getattr(app.state, 'tracking_only', False):
            enabled = True
        win = self.holder.get('window')
        if not win:
            return False
        if enabled == self.holder.get('library_mode', False):
            return enabled
        bridge = self.holder.get('resize_bridge')
        if not bridge:
            raise RuntimeError('The desktop window is still getting ready. Try again in a moment.')
        self.set_character_only(False)
        if enabled:
            self.holder['companion_bounds'] = self.window_bounds()
        self.holder['library_mode'] = enabled
        bridge.mode_request.emit(enabled)
        win.evaluate_js('window.applyLibraryMode(' + ('true' if enabled else 'false') + '); void 0;')
        return enabled

    def set_screen_access(self, enabled):
        self.screen_access = bool(enabled)
        return self.screen_access

    def cursor_position(self):
        if sys.platform == 'darwin':
            from macos_support import cursor_position
            return cursor_position()
        if sys.platform != 'win32':
            return None
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL('user32')
        user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        point = wintypes.POINT()
        if not user32.GetCursorPos(ctypes.byref(point)):
            return None
        left, top = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
        width, height = max(1, user32.GetSystemMetrics(78)), max(1, user32.GetSystemMetrics(79))
        return {'x': (point.x - left) / width * 2 - 1, 'y': (point.y - top) / height * 2 - 1}

    def game_status(self):
        from game_detection import game_session
        result = game_session(getattr(self, '_tracked_game', None))
        self._tracked_game = result if result['detected'] else None
        return result

    def screen_snapshot(self):
        if not getattr(self, 'screen_access', False):
            return None
        import base64
        import io
        from PIL import ImageGrab
        image = ImageGrab.grab().convert('RGB')
        # Screen access shares the visible desktop, including Sakura when it
        # is on screen. Masking our whole window hid the entire capture when
        # maximized and also hid content behind a transparent companion.
        image.thumbnail((1600, 1200))
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=82)
        return base64.b64encode(output.getvalue()).decode('ascii')


def run_server():
    """Run FastAPI uvicorn in background thread."""
    global _desktop_server
    try:
        _desktop_server = uvicorn.Server(uvicorn.Config(
            app,
            host="127.0.0.1",
            port=gui_server.port,
            log_level="warning",
        ))
        _desktop_server.run()
    except OSError:
        pass


def exclude_companion_from_capture():
    """Ask Windows to omit this process's visible top-level windows from captures."""
    if sys.platform != 'win32':
        return
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    @callback_type
    def visit(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == os.getpid() and user32.IsWindowVisible(hwnd):
            if not user32.SetWindowDisplayAffinity(hwnd, 0x11):
                print('  Windows could not exclude a companion window from capture.', flush=True)
        return True
    user32.EnumWindows(visit, 0)


def main():
    print()
    print("  🌸 Sakura — Transparent Desktop Companion")
    from PySide6 import __version__ as qt_version
    print(f"  Desktop renderer: Qt {qt_version}")
    print("  ──────────────────────────────────────────")

    # Start FastAPI server in background only if not already running
    if gui_server.select_port():
        print(f"  Found existing Sakura backend on {gui_server.url()}")
    else:
        print("  Initializing local backend server...")
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        # Wait only until the server binds instead of an unconditional delay.
        import socket
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(('127.0.0.1', gui_server.port), timeout=0.1):
                    break
            except OSError:
                time.sleep(0.05)

    # Holder to pass window reference to Api
    library_mode = os.environ.get('SAKURA_UPLOAD_UI') == '1' or bool(getattr(app.state, 'tracking_only', False))
    holder = {'library_mode': library_mode}
    api = DesktopApi(holder)

    # Detect screen size or use default companion dimensions
    # A pleasant floating aspect ratio: 460px wide by 760px tall
    window_width = 1100 if library_mode else 460
    window_height = 760

    print("  Spawning transparent floating window...")
    # WebView2 persists its HTTP cache between launches. Tie the document URL
    # to the current UI file so an app update cannot reopen stale HTML (which
    # otherwise also keeps stale module URLs and tracking controls).
    try:
        ui_revision = (Path(__file__).parent / 'static' / 'index.html').stat().st_mtime_ns
    except OSError:
        ui_revision = int(time.time())
    page_mode = 'library=1&upload=1' if library_mode else 'desktop=1&companion=1'
    page_url = f'http://{gui_server.HOST}:{gui_server.port}/?{page_mode}&ui={ui_revision}'
    webview.settings['DRAG_REGION_DIRECT_TARGET_ONLY'] = True
    window = webview.create_window(
        title=APP_DISPLAY_NAME,
        url=page_url,
        width=window_width,
        height=window_height,
        frameless=True,
        easy_drag=False,
        resizable=True,
        min_size=(320, 400),
        transparent=True,
        shadow=False,
        on_top=not library_mode,
        maximized=library_mode,
        js_api=api,
        background_color="#000000",
    )
    holder["window"] = window

    def setup_native_resizing():
        from PySide6.QtCore import QObject, Signal, Slot, Qt, QTimer
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication
        native = window.native
        application = QApplication.instance()
        application.setApplicationName(APP_DISPLAY_NAME)
        application.setApplicationDisplayName(APP_DISPLAY_NAME)
        application.setOrganizationName('Sakura')
        application.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        native.setWindowTitle(APP_DISPLAY_NAME)
        native.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        profile = native.webview.page().profile()
        profile.setCachePath(str(Path(__file__).parent / 'desktop-profile' / 'http-cache'))
        if sys.platform == 'win32':
            from window_identity import set_taskbar_identity
            set_taskbar_identity(int(native.winId()), APP_USER_MODEL_ID,
                APP_LAUNCHER_PATH, APP_ICON_PATH)
        class ResizeBridge(QObject):
            request = Signal(str)
            input_request = Signal(bool)
            mode_request = Signal(bool)
            maximize_request = Signal()
            def __init__(self):
                super().__init__()
                self.request.connect(self.resize_window)
                self.input_request.connect(self.set_input_transparency)
                self.mode_request.connect(self.set_mode)
                self.maximize_request.connect(self.toggle_maximize)

            @Slot()
            def toggle_maximize(self):
                if holder.get('library_maximized', holder.get('library_mode', False)):
                    native.setWindowState(Qt.WindowNoState)
                    if sys.platform == 'win32':
                        from window_input import restore_window
                        restore_window(int(native.winId()))
                    display = QApplication.screenAt(native.pos()) or QApplication.primaryScreen()
                    bounds = display.availableGeometry()
                    saved = holder.get('library_bounds', {})
                    width = min(saved.get('width', 1100), bounds.width())
                    height = min(saved.get('height', 760), bounds.height())
                    left = max(bounds.x(), min(saved.get('x', bounds.x() + (bounds.width()-width)//2), bounds.right()-width+1))
                    top = max(bounds.y(), min(saved.get('y', bounds.y() + (bounds.height()-height)//2), bounds.bottom()-height+1))
                    native.setGeometry(left, top, width, height)
                    native.showNormal()
                    # Apply the restored geometry after Windows has processed
                    # the state transition for this transparent Qt window.
                    QTimer.singleShot(100, lambda: native.setGeometry(left, top, width, height))
                else:
                    holder['library_bounds'] = {'x': native.x(), 'y': native.y(),
                        'width': native.width(), 'height': native.height()}
                    native.showMaximized()
                holder['library_maximized'] = native.isMaximized()
                self.update_maximize_control(holder['library_maximized'])

            def update_maximize_control(self, maximized):
                # evaluate_js waits for Qt to deliver its result. Running it in
                # this UI-thread slot would deadlock the renderer.
                threading.Thread(target=window.evaluate_js, args=(
                    'window.updateMaximizeControl?.(' + ('true' if maximized else 'false') + '); void 0;',
                ), daemon=True).start()

            @Slot(bool)
            def set_mode(self, library):
                # Keep the same native window and WebEngine compositor surface.
                # setWindowFlag recreates a translucent Qt window on Windows,
                # causing flashing and stale alpha after changing modes.
                native.setWindowState(Qt.WindowNoState)
                if sys.platform != 'win32':
                    native.setWindowFlag(Qt.WindowStaysOnTopHint, not library)
                native.is_fullscreen = False
                if library:
                    # pywebview uses `native.screen` for a QRect, shadowing
                    # QWidget.screen(). Ask QApplication for the display.
                    display = QApplication.screenAt(native.pos()) or QApplication.primaryScreen()
                    native.setGeometry(display.availableGeometry())
                    native.showMaximized()
                else:
                    native.showNormal()
                    if sys.platform == 'win32':
                        from window_input import restore_window
                        restore_window(int(native.winId()))
                    bounds = holder.get('companion_bounds', {'width': 460, 'height': 760, 'x': 80, 'y': 80})
                    def restore_companion_geometry():
                        if not holder.get('library_mode'):
                            native.setGeometry(int(bounds['x']), int(bounds['y']), int(bounds['width']), int(bounds['height']))
                    restore_companion_geometry()
                    # Windows delivers the maximize/restore placement after
                    # this slot. Apply the requested bounds after that event.
                    QTimer.singleShot(100, restore_companion_geometry)
                if sys.platform == 'win32':
                    from window_input import set_topmost
                    if not set_topmost(int(native.winId()), not library):
                        print('  Could not update companion window z-order.', flush=True)
                print('  Window mode: ' + ('model library' if library else 'desktop companion'), flush=True)
                holder['library_maximized'] = library
                self.update_maximize_control(library)

            @Slot(bool)
            def set_input_transparency(self, enabled):
                if sys.platform == 'darwin':
                    # Supported on Qt/macOS; Windows retains its compositor-safe Win32 path.
                    native.setWindowFlag(Qt.WindowTransparentForInput, enabled)
                    native.show()
                if sys.platform == 'win32':
                    from window_input import set_click_through
                    if not set_click_through(int(native.winId()), enabled):
                        print('  Could not change companion click-through state.', flush=True)

            @Slot(str)
            def resize_window(self, edge):
                # The webview bridge is asynchronous. Ignore requests that
                # arrive after the user has already released the mouse.
                if not (QApplication.mouseButtons() & Qt.LeftButton):
                    return
                edges = Qt.Edges()
                for letter, flag in [('n', Qt.TopEdge), ('s', Qt.BottomEdge), ('e', Qt.RightEdge), ('w', Qt.LeftEdge)]:
                    if letter in edge:
                        edges |= flag
                handle = native.windowHandle()
                if handle:
                    handle.startSystemResize(edges)

        bridge = ResizeBridge()
        bridge.moveToThread(native.thread())
        holder['resize_bridge'] = bridge
        # Sample native title/flower dragging on Qt's thread. JavaScript cannot
        # see mouse movement while the OS owns a system window drag. Async page
        # dispatch avoids blocking the compositor or spawning per-move workers.
        drag_position = [native.x(), native.y()]

        def update_hair_drag():
            x, y = native.x(), native.y()
            dx, dy = x - drag_position[0], y - drag_position[1]
            drag_position[:] = [x, y]
            if not (dx or dy):
                return
            from PySide6.QtWidgets import QApplication
            if not QApplication.mouseButtons() & Qt.MouseButton.LeftButton:
                return
            # Ignore geometry jumps from restore/mode changes.
            if abs(dx) + abs(dy) > 300:
                return
            native.webview.page().runJavaScript(
                "window.dispatchEvent(new CustomEvent('sakura-window-drag', {detail:{dx:%d,dy:%d}}));" % (dx, dy))

        drag_timer = QTimer(native)
        drag_timer.setInterval(50)
        drag_timer.timeout.connect(update_hair_drag)
        drag_timer.start()
        holder['hair_drag_timer'] = drag_timer
        print('  Native window controls ready.', flush=True)

    # before_show runs synchronously on Qt's UI thread.
    window.events.before_show += setup_native_resizing
    window.events.loaded += lambda: window.evaluate_js(
        'window.updateMaximizeControl?.(' + ('true' if holder.get('library_mode') else 'false') + '); void 0;')

    overlay_stopped = threading.Event()
    window.events.closed += overlay_stopped.set

    def release_owned_services():
        if _desktop_server is not None:
            _desktop_server.should_exit = True
        from ollama_runtime import stop
        from rvc_manager import stop_rvc_service
        # Independent workers release concurrently: a starting RVC lock cannot
        # prevent the LLM job from closing before the shutdown deadline.
        workers = [threading.Thread(target=fn, daemon=True) for fn in (stop, stop_rvc_service)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=3)

    def finish_closed_window():
        from desktop_shutdown import arm_shutdown
        print('  Companion closed: releasing owned services.', flush=True)
        arm_shutdown(release_owned_services)

    window.events.closed += finish_closed_window

    def maintain_game_overlay():
        if sys.platform != 'win32':
            return
        import ctypes
        from ctypes import wintypes
        from game_detection import foreground_game
        user = ctypes.WinDLL('user32')
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user.IsWindowVisible.argtypes = [wintypes.HWND]
        user.IsIconic.argtypes = [wintypes.HWND]
        user.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        @callback_type
        def raise_companion(hwnd, _):
            owner = wintypes.DWORD()
            user.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            title = ctypes.create_unicode_buffer(128)
            user.GetWindowTextW(hwnd, title, len(title))
            if owner.value == os.getpid() and title.value == APP_DISPLAY_NAME and user.IsWindowVisible(hwnd) and not user.IsIconic(hwnd):
                # Qt already keeps the companion topmost. Reapplying this on
                # every poll can invalidate the transparent compositor surface
                # and flash the entire window. Restore only a lost topmost bit.
                if not user.GetWindowLongPtrW(hwnd, -20) & 0x00000008:
                    user.SetWindowPos(hwnd, wintypes.HWND(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0008)
            return True
        while not overlay_stopped.wait(1.0):
            try:
                if not getattr(app.state, 'tracking_only', False) and not holder.get('library_mode') and foreground_game()['detected'] and not (user.GetAsyncKeyState(0x01) & 0x8000):
                    user.EnumWindows(raise_companion, 0)
            except Exception as exc:
                print(f'  Overlay positioning: {exc}', flush=True)

    window.events.loaded += lambda: threading.Thread(target=maintain_game_overlay, daemon=True).start()

    holder['window'] = window

    def register_companion_hotkey():
        if sys.platform == 'darwin':
            from macos_support import start_hotkey
            holder['mac_hotkey'] = start_hotkey(
                lambda: window.evaluate_js('window.toggleCompanionView?.()'),
                __import__('companion_hotkey').parse_hotkey(get_settings().get('transparency_hotkey', ''))[3])
            api.hotkey_registered = holder['mac_hotkey'] is not None
            return
        if sys.platform != 'win32':
            return
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel = ctypes.windll.kernel32
        queued_message = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(queued_message), None, 0, 0, 0)
        from companion_hotkey import parse_hotkey, DEFAULT_HOTKEY
        holder['hotkey_update_lock'] = threading.Lock()
        holder['hotkey_thread_id'] = kernel.GetCurrentThreadId()
        active_id = 1
        try: active, flags, vk, _ = parse_hotkey(get_settings().get('transparency_hotkey', ''))
        except ValueError: active, flags, vk, _ = parse_hotkey('')
        api.hotkey_registered = bool(user32.RegisterHotKey(None, active_id, flags | 0x4000, vk))
        if not api.hotkey_registered and active != DEFAULT_HOTKEY:
            active, flags, vk, _ = parse_hotkey('')
            api.hotkey_registered = bool(user32.RegisterHotKey(None, active_id, flags | 0x4000, vk))
        message = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == 0x8001:
                    request = holder.get('hotkey_request')
                    if not request: continue
                    canonical, flags, vk = request['shortcut']
                    new_id = 2 if active_id == 1 else 1
                    if canonical == active and api.hotkey_registered:
                        result = {'ok':True,'hotkey':active}
                    elif user32.RegisterHotKey(None, new_id, flags | 0x4000, vk):
                        user32.UnregisterHotKey(None, active_id)
                        active_id, active = new_id, canonical
                        api.hotkey_registered = True
                        result = {'ok':True,'hotkey':active}
                    else:
                        result = {'ok':False,'error':'That shortcut is used by another application. Your previous shortcut remains active.'}
                    request['result'] = result
                    request['done'].set()
                elif message.message == 0x0312:
                    try: window.evaluate_js('window.toggleCompanionView?.()')
                    except Exception: break
        finally:
            user32.UnregisterHotKey(None, active_id)
            api.hotkey_registered = False

    def stop_companion_hotkey():
        if holder.get('mac_hotkey') is not None:
            holder['mac_hotkey'].stop()
            api.hotkey_registered = False
        thread_id = holder.get('hotkey_thread_id')
        if thread_id and sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(thread_id, 0x0012, 0, 0)

    window.events.closed += stop_companion_hotkey

    window.events.loaded += lambda: threading.Thread(
        target=register_companion_hotkey, daemon=True
    ).start()

    # Start pywebview main event loop
    try:
        # Qt installs this icon while constructing the native window, before
        # showing it. Late synchronous Win32 icon messages can stall input.
        webview.start(gui='qt', debug=False, icon=str(APP_ICON_PATH),
                      private_mode=False, storage_path=str(Path(__file__).parent / 'desktop-profile'))
    finally:
        # Finish the owned backend before Python shuts down its executors.
        # Otherwise a closing window can leave a half-alive HTTP server that
        # accepts requests but cannot synthesize voice or schedule work.
        if _desktop_server is not None:
            _desktop_server.should_exit = True
            if 'server_thread' in locals():
                server_thread.join(timeout=10)
        from ollama_runtime import stop
        from rvc_manager import stop_rvc_service
        stop_rvc_service()
        stop()


if __name__ == "__main__":
    main()
