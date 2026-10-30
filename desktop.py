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
INSTANCE_INDEX=1
if EDITION=='vtuber' or os.environ.get('SAKURA_VTUBER_INSTANCE')=='1':
    from vtuber_instances import claim_instance
    try:INSTANCE_INDEX=claim_instance(Path(__file__).parent)
    except RuntimeError as error:
        if sys.platform=='win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(0,str(error),'Sakura VTuber',0x40)
        raise SystemExit(0)
from vtuber_instances import instance_profile
PROFILE_DIR=instance_profile(Path(__file__).parent,INSTANCE_INDEX)
APP_DISPLAY_NAME = DISPLAY_NAME + (f' · {INSTANCE_INDEX}' if INSTANCE_INDEX>1 else '')
APP_USER_MODEL_ID = 'Sakura.VTuber' if EDITION=='vtuber' else 'Sakura.DesktopCompanion'
from app_branding import icon_path
APP_ICON_PATH = icon_path(Path(__file__).parent, EDITION)
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
    if EDITION != 'vtuber' and '--ui-disable-partial-swap' not in _graphics_flags:
        _graphics_flags += ' --ui-disable-partial-swap'
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = _graphics_flags.strip()
    if EDITION != 'vtuber' and '--disable-direct-composition' not in _graphics_flags:
        # Qt already presents the WebEngine texture into its layered window.
        # Avoid a second Windows surface presenter for that alpha texture;
        # ANGLE/D3D11 still renders models on the GPU.
        _graphics_flags += ' --disable-direct-composition'
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = _graphics_flags.strip()
    if '--use-angle=' not in _graphics_flags:
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = (_graphics_flags + ' --use-gl=angle --use-angle=d3d11').strip()
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    if EDITION != 'vtuber':
        print('  Companion compositor: full swaps, DirectComposition disabled; GPU rendering retained.', flush=True)

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
    def windows_startup_status(self):
        try:
            from windows_startup import status
            return status()
        except Exception:return {'supported':False,'enabled':False,'error':'Could not read Windows startup settings.'}

    def set_windows_startup(self,enabled):
        try:
            from windows_startup import configure
            return configure(enabled)
        except Exception as error:return {'error':str(error)}

    def new_vtuber_instance(self):
        try:
            from vtuber_instances import spawn_instance, claim_instance
            if 'SAKURA_INSTANCE_INDEX' not in os.environ:claim_instance(Path(__file__).parent)
            process=spawn_instance(Path(__file__).parent)
            return {'ok':True,'pid':process.pid}
        except Exception as error:return {'error':str(error)}

    def install_virtual_camera_driver(self):
        try:
            from sakura_camera_native import install_driver
            return install_driver()
        except Exception as error:
            return {'error': str(error)}

    def uninstall_virtual_camera_driver(self):
        try:
            from sakura_camera_native import uninstall_driver
            return uninstall_driver()
        except Exception as error:
            return {'error': str(error)}

    def virtual_camera_driver_status(self):
        try:
            from sakura_camera_native import CAMERA_NAME, driver_installed
            return {'installed': bool(driver_installed()), 'device': CAMERA_NAME}
        except Exception as error:
            return {'error': str(error)}

    def __init__(self, window_holder):
        self.holder = window_holder

    def wake_state(self):
        return self.holder['wake'].state()

    def install_wake_pack(self):
        try:return self.holder['wake'].install()
        except Exception as error:return {'error':str(error)}

    def set_wake_listener(self, enabled, phrase='hey sakura'):
        try:
            wake=self.holder['wake']
            if enabled:
                if EDITION=='vtuber' or getattr(app.state,'tracking_only',False):raise RuntimeError('Wake listening is available in Companion AI mode.')
                return wake.start(phrase)
            wake.stop()
            return wake.state()
        except Exception as error:return {'error':str(error)}

    def pause_wake_listener(self, paused):
        self.holder['wake'].pause(paused)
        return True

    def end_chat_session(self):
        win=self.holder.get('window')
        if win and EDITION!='vtuber':
            # closing can run on Qt's GUI thread. Never synchronously wait for
            # JavaScript on that same thread or close/restart deadlocks.
            def notify():
                try:win.evaluate_js("window.dispatchEvent(new Event('sakura-chat-session-ended')); void 0;")
                except Exception:pass
            threading.Thread(target=notify,name='sakura-session-close',daemon=True).start()

    def close(self):
        """Close the desktop companion window."""
        win = self.holder.get("window")
        if win:
            self.end_chat_session()
            if self.holder.get('wake') and self.holder['wake'].state()['enabled'] and self.holder.get('tray_available'):
                self.holder['resize_bridge'].hide_request.emit()
                return
            win.destroy()

    def open_pmx_editor(self, model_path):
        from pmx_editor import open_model, find_editor, model_file
        model_file(model_path)
        if sys.platform != 'win32':
            return open_model(model_path)
        configured = get_settings().get('pmx_editor_path')
        editor = find_editor(configured)
        if editor is None:
            win = self.holder.get('window')
            if not win:
                raise RuntimeError('Open Sakura’s desktop window to select PMX Editor.')
            selected = win.create_file_dialog(webview.FileDialog.OPEN,
                allow_multiple=False, file_types=('PMX Editor (PmxEditor.exe)',))
            if not selected:
                return {'cancelled': True}
            editor = find_editor(selected[0])
            if editor is None:
                raise ValueError('Choose PmxEditor.exe from its complete installation folder.')
            from app import save_settings
            save_settings({'pmx_editor_path': str(editor)})
        return open_model(model_path, str(editor))

    def capture_pmx_appearance_reference(self, model_path, direction):
        """Read a reference from an owned PMX Editor, without editing source art."""
        from pmx_appearance_reference import capture_reference
        return capture_reference(model_path, direction, get_settings().get('pmx_editor_path'))

    def platform_capabilities(self):
        return {'platform': sys.platform, 'pmx_editor': sys.platform == 'win32','mmd':sys.platform=='win32'}

    def open_mmd(self,model_path):
        from mmd_launcher import find_mmd,open_mmd
        from pmx_editor import model_file
        model_file(model_path)
        path=find_mmd(get_settings().get('mmd_path'))
        if path is None:
            win=self.holder.get('window')
            if not win:raise RuntimeError('Open Sakura’s desktop window to select MikuMikuDance.')
            selected=win.create_file_dialog(webview.FileDialog.OPEN,allow_multiple=False,
                file_types=('MikuMikuDance (MikuMikuDance.exe)',))
            if not selected:return {'cancelled':True}
            path=find_mmd(selected[0])
            if path is None:raise ValueError('Choose MikuMikuDance.exe with its Data folder alongside it.')
            from app import save_settings
            save_settings({'mmd_path':str(path)})
        return open_mmd(str(path),model_path)

    def install_rvc_runtime(self):
        if sys.platform!='win32':raise RuntimeError('Use setup-rvc-macos.command on macOS.')
        from native_consent import confirm
        script=Path(__file__).parent/'setup-rvc-windows.ps1'
        if not script.is_file():raise RuntimeError('RVC setup is missing. Repair this Sakura installation.')
        if not confirm('Install optional RVC',{'downloads':'PyTorch, RVC dependencies and checksum-verified base models. Several GB may be required.','script':str(script)}):return {'cancelled':True}
        import subprocess
        executable=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
        subprocess.Popen([str(executable),'-NoProfile','-NoExit','-ExecutionPolicy','Bypass','-File',str(script)],cwd=str(script.parent),creationflags=subprocess.CREATE_NEW_CONSOLE)
        return {'opened':True}

    def copy_text(self,text):
        from native_clipboard import copy_text
        return copy_text(text)

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

    def choose_local_gguf_files(self):
        import webview
        win=webview.windows[0] if webview.windows else None
        if not win:return []
        selected=win.create_file_dialog(webview.FileDialog.OPEN,allow_multiple=True,file_types=('GGUF models (*.gguf)',))
        return list(selected or [])

    def choose_nvidia_expressionapp_folder(self):
        """Choose MXTracker/v2 (or v1) from the user's Steam DLC install."""
        win=self.holder.get('window')
        if not win:return None
        selected=win.create_file_dialog(webview.FileDialog.FOLDER)
        return selected[0] if selected else None

    def minimize(self):
        """Minimize the companion."""
        if EDITION!='vtuber' and not getattr(app.state,'tracking_only',False):
            return self.set_library_mode(False)
        win = self.holder.get("window")
        if win:
            bridge=self.holder.get('resize_bridge')
            if bridge:bridge.minimize_request.emit()
            else:win.minimize()

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

    def set_surface_transparency(self, enabled: bool):
        bridge = self.holder.get('resize_bridge')
        if bridge and EDITION != 'vtuber':
            bridge.surface_request.emit(bool(enabled))
        return True

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
        if not win:
            return {'error': 'The desktop window is not ready.'}
        start = MODELS_DIR / kind
        start.mkdir(parents=True, exist_ok=True)
        # The studio panel offers import in the small companion window as well,
        # which can sit behind other apps and never get the dialog's focus.
        if not self.holder.get('library_mode'):
            win.show()
            win.restore()
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

    def choose_mobile_model_package(self,kind):
        """The local user selects the complete folder; the phone cannot specify PC paths."""
        import secrets
        if kind not in ('pmx','vrm','live2d'):return {'error':'Choose PMX, VRM or Live2D.'}
        win=self.holder.get('window')
        if not win:return {'error':'The desktop window is not ready.'}
        try:
            win.show();win.restore()
            selection=win.create_file_dialog(webview.FileDialog.OPEN if kind=='vrm' else webview.FileDialog.FOLDER,
                allow_multiple=False,file_types=('VRM models (*.vrm)',) if kind=='vrm' else ())
            if not selection:return {'cancelled':True}
            folder=Path(selection[0]).resolve()
            entries=[folder] if kind=='vrm' else sorted(p for p in folder.rglob('*') if p.is_file() and (p.suffix.lower()=='.pmx' if kind=='pmx' else p.name.lower().endswith('.model3.json')))
            if not entries:raise ValueError('No '+kind.upper()+' model was found in that folder.')
            identifier=secrets.token_hex(16);self._mobile_selection=(identifier,folder,kind,entries)
            return {'selection':identifier,'entries':[p.name if kind=='vrm' else p.relative_to(folder).as_posix() for p in entries],
                    'folder':folder.name,'format':kind}
        except Exception as error:return {'error':str(error)}

    def send_mobile_model_package(self,selection,index,request_id):
        from mobile_link import link
        try:
            chosen=getattr(self,'_mobile_selection',None)
            if not chosen or chosen[0]!=selection:raise ValueError('Choose the model folder again.')
            _,folder,kind,entries=chosen
            if not isinstance(index,int) or not 0<=index<len(entries):raise ValueError('Choose a model from the selected folder.')
            result=link.stage_selection(entries[index],folder,kind,request_id);self._mobile_selection=None
            return {'model':result}
        except Exception as error:return {'error':str(error)}

    def show_phone_transfer(self):
        win=self.holder.get('window')
        if win:
            win.show();win.restore()
        return True

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

    def set_brand_mode(self, tracking):
        bridge=self.holder.get('resize_bridge')
        if not bridge:return False
        bridge.brand_request.emit(bool(tracking))
        return True

    def set_screen_access(self, enabled):
        self.screen_access = bool(enabled)
        return self.screen_access

    def cursor_position(self):
        from screen_cursor import position
        return position()

    def game_status(self):
        from game_detection import game_session
        result = game_session(getattr(self, '_tracked_game', None))
        self._tracked_game = result if result['detected'] else None
        # Game Mode uses the same live adapter counters as PC status to avoid
        # switching providers based on utilization guesses or stale readings.
        if sys.platform == 'win32':
            try:
                from hardware_metrics import sample_windows
                result['gpus'] = sample_windows().get('gpus', [])
            except (OSError, RuntimeError, AttributeError):
                result['gpus'] = []
        return result

    def screen_snapshot(self):
        if not getattr(self, 'screen_access', False):
            return None
        import base64
        import io
        from PIL import ImageGrab
        try:
            image = ImageGrab.grab().convert('RGB')
        except OSError:
            # Lock-screen/display transitions can temporarily deny capture.
            # Report no frame; never reuse a stale image or spam tracebacks.
            return None
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
    try:
        from private_storage import protect_installation_state
        protect_installation_state(Path(__file__).parent)
    except OSError:
        if sys.platform=='win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,'Sakura cannot protect or write its private data in this folder. Install Sakura for your Windows user in LocalAppData, or choose a folder you own. Your existing files were kept.','Sakura — private storage',0x10)
        return
    print()
    print("  🌸 Sakura — Transparent Desktop Companion")
    from PySide6 import __version__ as qt_version
    print(f"  Desktop renderer: Qt {qt_version}")
    print("  ──────────────────────────────────────────")

    # Start FastAPI server in background only if not already running
    try:existing_backend=gui_server.select_port()
    except RuntimeError as error:
        if sys.platform=='win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,str(error)+'\nClose another Sakura window or the app occupying these ports, then try again.','Sakura — connection unavailable',0x10)
        return
    if existing_backend:
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
    agent_mode = getattr(app.state, 'startup_mode', '') == 'agent'
    library_mode = os.environ.get('SAKURA_UPLOAD_UI') == '1' or bool(getattr(app.state, 'tracking_only', False)) or agent_mode
    holder = {'library_mode': library_mode}
    from desktop_wake import DesktopWake
    def wake_command(text):
        import json
        bridge=holder.get('resize_bridge')
        if bridge and holder.pop('wake_hidden',False):bridge.focus_request.emit()
        result=holder['window'].evaluate_js('window.receiveDesktopWakeCommand?.('+json.dumps(text)+')')
        if not result:holder['wake'].pause(False)
    holder['wake']=DesktopWake(Path(__file__).parent,wake_command)

    from window_placement import read_placement
    placement_file=PROFILE_DIR/'companion-placement.json'
    saved_placement=read_placement(placement_file)
    if saved_placement:holder['companion_bounds']=saved_placement
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
    page_mode = 'library=1&upload=1' if library_mode and not agent_mode else 'desktop=1&companion=1'
    page_url = f'http://{gui_server.HOST}:{gui_server.port}/?{page_mode}&ui={ui_revision}' + ('&agent=1' if agent_mode else '')
    if getattr(app.state,'tracking_only',False):page_url+='&tracking=1'
    page_url+=f'&instance={INSTANCE_INDEX}'
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
        from PySide6.QtGui import QIcon, QColor
        from PySide6.QtWidgets import QApplication
        native = window.native
        if EDITION != 'vtuber':
            # WA_TranslucentBackground also enables WA_NoSystemBackground.
            # Re-enable background clearing: otherwise WebEngine's changed
            # alpha tiles are painted over stale menus and old avatar frames.
            native.setAttribute(Qt.WA_NoSystemBackground, False)
            native.setAttribute(Qt.WA_OpaquePaintEvent, False)
            # Preserve pywebview's alpha-capable child surface. Turning off
            # WA_TranslucentBackground makes character-only mode opaque even
            # when both the document and WebEngine page are transparent.
            native.webview.setAttribute(Qt.WA_NoSystemBackground, False)
            native.webview.setAttribute(Qt.WA_OpaquePaintEvent, False)
            # Chromium invalidates only damaged tiles. On a layered Windows
            # window, Qt must also clear the complete backing store before
            # blending that frame or dismissed controls remain underneath.
            native.webview.page().setBackgroundColor(QColor('#090713'))
            surface_timer = QTimer(native)
            surface_timer.setInterval(33)
            surface_timer.timeout.connect(native.update)
            holder['surface_timer'] = surface_timer
        application = QApplication.instance()
        application.setApplicationName(APP_DISPLAY_NAME)
        application.setApplicationDisplayName(APP_DISPLAY_NAME)
        application.setOrganizationName('Sakura')
        application.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        native.setWindowTitle(APP_DISPLAY_NAME)
        native.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        profile = native.webview.page().profile()
        profile.setCachePath(str(PROFILE_DIR / 'http-cache'))
        if INSTANCE_INDEX>1:profile.setPersistentStoragePath(str(PROFILE_DIR/'browser-storage'))
        if sys.platform == 'win32':
            from window_identity import set_taskbar_identity
            set_taskbar_identity(int(native.winId()), APP_USER_MODEL_ID,
                APP_LAUNCHER_PATH, APP_ICON_PATH)
        class ResizeBridge(QObject):
            request = Signal(str)
            focus_request = Signal()
            minimize_request = Signal()
            hide_request = Signal()
            input_request = Signal(bool)
            surface_request = Signal(bool)
            mode_request = Signal(bool)
            brand_request = Signal(bool)
            maximize_request = Signal()
            def __init__(self):
                super().__init__()
                self.focus_request.connect(self.focus_window)
                self.minimize_request.connect(native.showMinimized)
                self.hide_request.connect(self.hide_window)
                self.request.connect(self.resize_window)
                self.input_request.connect(self.set_input_transparency)
                self.surface_request.connect(self.set_surface_transparency)
                self.mode_request.connect(self.set_mode)
                self.brand_request.connect(self.set_brand)
                self.maximize_request.connect(self.toggle_maximize)

            @Slot(bool)
            def set_brand(self, tracking):
                path=icon_path(Path(__file__).parent,EDITION,tracking)
                holder['active_icon_path']=path
                icon=QIcon(str(path))
                native.setWindowIcon(icon)
                application.setWindowIcon(icon)
                if holder.get('tray'):holder['tray'].setIcon(icon)
                if sys.platform=='win32':
                    from window_identity import set_taskbar_identity
                    set_taskbar_identity(int(native.winId()),APP_USER_MODEL_ID,APP_LAUNCHER_PATH,path)

            @Slot()
            def hide_window(self):
                holder['wake_hidden']=True
                native.webview.page().runJavaScript("window.dispatchEvent(new CustomEvent('sakura-native-visibility',{detail:{hidden:true}}))")
                native.hide()

            @Slot()
            def focus_window(self):
                holder['wake_hidden']=False
                if native.isMinimized():native.showNormal()
                else:native.show()
                native.webview.show()
                native.webview.update()
                native.webview.page().runJavaScript("window.dispatchEvent(new CustomEvent('sakura-native-visibility',{detail:{hidden:false}}))")
                native.raise_()
                native.activateWindow()
                if sys.platform=='win32':
                    import ctypes
                    ctypes.windll.user32.SetForegroundWindow.argtypes=[ctypes.c_void_p]
                    ctypes.windll.user32.SetForegroundWindow(int(native.winId()))

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
                holder['geometry_transition_until']=time.monotonic()+.5
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
                    from window_placement import compact_geometry
                    saved=holder.get('companion_bounds')
                    display=QApplication.screenAt(native.pos()) or QApplication.primaryScreen()
                    if saved:
                        from PySide6.QtCore import QPoint
                        display=QApplication.screenAt(QPoint(int(saved['x']+saved['width']/2),int(saved['y']+saved['height']/2))) or display
                    area=display.availableGeometry()
                    bounds=compact_geometry({'x':area.x(),'y':area.y(),'width':area.width(),'height':area.height()},saved)
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
            def set_surface_transparency(self, enabled):
                native.webview.page().setBackgroundColor(
                    QColor(Qt.transparent) if enabled else QColor('#090713'))
                timer = holder.get('surface_timer')
                if timer:
                    timer.start() if enabled else timer.stop()
                native.update()

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
        bridge.set_brand(bool(getattr(app.state,'tracking_only',False)))
        if not holder.get('library_mode'):
            from window_placement import compact_geometry
            from PySide6.QtCore import QPoint
            saved=holder.get('companion_bounds')
            display=QApplication.screenAt(native.pos()) or QApplication.primaryScreen()
            if saved:
                display=QApplication.screenAt(QPoint(saved['x']+saved['width']//2,saved['y']+saved['height']//2)) or display
            area=display.availableGeometry()
            initial=compact_geometry({'x':area.x(),'y':area.y(),'width':area.width(),'height':area.height()},saved)
            native.setGeometry(initial['x'],initial['y'],initial['width'],initial['height'])
        # Sample native title/flower dragging on Qt's thread. JavaScript cannot
        # see mouse movement while the OS owns a system window drag. Async page
        # dispatch avoids blocking the compositor or spawning per-move workers.
        drag_position = [native.x(), native.y()]

        def update_hair_drag():
            x, y = native.x(), native.y()
            dx, dy = x - drag_position[0], y - drag_position[1]
            drag_position[:] = [x, y]
            pressed=bool(QApplication.mouseButtons() & Qt.MouseButton.LeftButton)
            if not holder.get('library_mode') and time.monotonic()>holder.get('geometry_transition_until',0):
                geometry={'x':x,'y':y,'width':native.width(),'height':native.height()}
                previous=holder.get('last_compact_geometry')
                holder['last_compact_geometry']=geometry
                if pressed and previous and previous!=geometry:
                    holder['placement_pending']=geometry
                elif not pressed and holder.pop('placement_pending',None):
                    from window_placement import save_placement
                    holder['companion_bounds']=geometry
                    try:save_placement(placement_file,geometry)
                    except OSError as error:print(f'  Could not save Companion position: {error}',flush=True)
            if not (dx or dy):
                return
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
        last_visibility=[None]
        def update_native_visibility():
            hidden=not native.isVisible() or native.isMinimized()
            if hidden==last_visibility[0]:return
            last_visibility[0]=hidden
            native.webview.page().runJavaScript("window.dispatchEvent(new CustomEvent('sakura-native-visibility',{detail:{hidden:"+('true' if hidden else 'false')+"}}))")
            if hidden:holder['wake_hidden']=True
        visibility_timer=QTimer(native);visibility_timer.setInterval(500);visibility_timer.timeout.connect(update_native_visibility);visibility_timer.start();holder['visibility_timer']=visibility_timer

        if EDITION!='vtuber':
            from PySide6.QtWidgets import QSystemTrayIcon, QMenu
            from PySide6.QtGui import QAction
            if QSystemTrayIcon.isSystemTrayAvailable():
                tray=QSystemTrayIcon(QIcon(str(holder.get('active_icon_path',APP_ICON_PATH))),native)
                menu=QMenu();show_action=QAction('Open Sakura',menu);show_action.triggered.connect(holder['resize_bridge'].focus_window);menu.addAction(show_action)
                stop_action=QAction('Stop wake listening',menu)
                def stop_wake():
                    holder['wake'].stop()
                    threading.Thread(target=window.evaluate_js,args=("window.stopDesktopWakeFromTray?.()",),daemon=True).start()
                stop_action.triggered.connect(stop_wake);menu.addAction(stop_action)
                quit_action=QAction('Quit Sakura',menu)
                def quit_sakura():
                    holder['wake'].stop();window.destroy()
                quit_action.triggered.connect(quit_sakura);menu.addAction(quit_action)
                tray.setContextMenu(menu);tray.setToolTip('Sakura · wake listening off');tray.activated.connect(lambda reason:holder['resize_bridge'].focus_window() if reason==QSystemTrayIcon.ActivationReason.DoubleClick else None);tray.show()
                holder.update(tray=tray,tray_menu=menu,tray_available=True)
                def update_tray():
                    state=holder['wake'].state();tray.setToolTip('Sakura · '+state['status'][:110]);stop_action.setEnabled(state['enabled'])
                tray_timer=QTimer(native);tray_timer.setInterval(2000);tray_timer.timeout.connect(update_tray);tray_timer.start();holder['tray_timer']=tray_timer
        print('  Native window controls ready.', flush=True)

    # before_show runs synchronously on Qt's UI thread.
    window.events.before_show += setup_native_resizing
    window.events.loaded += lambda: window.evaluate_js(
        'window.updateMaximizeControl?.(' + ('true' if holder.get('library_mode') else 'false') + '); void 0;')
    # loaded callbacks run outside Qt's GUI thread. Use the existing QObject
    # bridge so activation follows normal UI-thread window handling.
    window.events.loaded += lambda: holder['resize_bridge'].focus_request.emit()

    def keep_wake_in_tray():
        api.end_chat_session()
        if holder.get('tray_available') and holder['wake'].state()['enabled']:
            holder['resize_bridge'].hide_request.emit()
            return False
    window.events.closing += keep_wake_in_tray

    overlay_stopped = threading.Event()
    window.events.closed += overlay_stopped.set

    def release_owned_services():
        holder['wake'].stop()
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
                      private_mode=False, storage_path=str(PROFILE_DIR))
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
