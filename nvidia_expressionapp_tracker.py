"""Adapter for the NVIDIA Broadcast Tracker ExpressionApp shipped with VTube Studio.

Sakura launches the user's locally installed ExpressionApp and consumes its
documented-by-community localhost UDP expression stream. The Steam DLC remains
user-installed and is never bundled or downloaded by Sakura.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import re

from nvidia_ar_tracker import AR_EXPRESSION_NAMES, expression_aliases


def detect_installed_folder():
    """Find the user's Steam-installed tracker DLC without crawling whole drives."""
    libraries = []
    if os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
                steam_root = Path(winreg.QueryValueEx(key, 'SteamPath')[0])
                libraries.append(steam_root)
        except (ImportError, OSError):
            pass
    for value in (os.environ.get('STEAM_PATH'), os.environ.get('PROGRAMFILES(X86)'), os.environ.get('PROGRAMFILES')):
        if value:
            libraries.append(Path(value))
    candidates = []
    for library in libraries:
        candidates.append(library)
        vdf = library / 'steamapps' / 'libraryfolders.vdf'
        try:
            contents = vdf.read_text(encoding='utf-8', errors='ignore')
            candidates.extend(Path(path.replace('\\\\', '\\')) for path in re.findall(r'"path"\s+"([^"]+)"', contents))
        except OSError:
            continue
    seen = set()
    for library in candidates:
        root = library / 'steamapps' / 'common' / 'VTube Studio' / 'VTube Studio_Data' / 'StreamingAssets' / 'MXTracker'
        for folder in (root / 'v2', root / 'v1', root):
            try:
                folder = folder.resolve()
            except OSError:
                continue
            if folder in seen:
                continue
            seen.add(folder)
            if (folder / 'ExpressionApp.exe').is_file() and (folder / 'models').is_dir():
                return str(folder)
    return ''


class ExpressionAppTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._process = None
        self._result = {}
        self._updated_at = 0.0
        self._error = ''
        self._folder = ''
        self._camera = 0
        self._fps = 0
        self._target_fps = 0

    @staticmethod
    def validate_folder(folder):
        root = Path(folder).expanduser().resolve()
        if root.is_file():
            root = root.parent
        if not (root / 'ExpressionApp.exe').is_file():
            root = next((candidate for candidate in (root / 'v2', root / 'v1')
                         if (candidate / 'ExpressionApp.exe').is_file()), root)
        exe = root / 'ExpressionApp.exe'
        models = root / 'models'
        if not exe.is_file() or not models.is_dir():
            raise ValueError('Choose the VTube Studio NVIDIA tracker folder containing ExpressionApp.exe and its models folder (usually MXTracker\\v2).')
        return root

    @staticmethod
    def decode_packet(packet):
        payload = json.loads(packet.rstrip(b'\0').decode('utf-8'))
        values = payload.get('exp')
        if not isinstance(values, list) or len(values) < len(AR_EXPRESSION_NAMES):
            raise ValueError('ExpressionApp packet did not contain the full blendshape array.')
        return {name: max(0.0, min(1.0, float(values[index])))
                for index, name in enumerate(AR_EXPRESSION_NAMES)}

    def start(self, folder, camera=0, width=1280, height=720, fps=30):
        if os.name != 'nt':
            raise RuntimeError('The VTube Studio NVIDIA Broadcast Tracker package runs only on Windows.')
        root = self.validate_folder(folder)
        camera = max(0, min(5, int(camera)))
        width, height = (1280, 720) if (int(width), int(height)) not in ((640, 480), (1280, 720), (1920, 1080)) else (int(width), int(height))
        fps = max(15, min(60, int(fps)))
        self.stop()
        port = 9140 + camera
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(('127.0.0.1', port))
        except OSError as error:
            sock.close()
            raise RuntimeError(f'Could not listen for NVIDIA tracker data on localhost UDP {port}: {error}') from error
        args = [str(root / 'ExpressionApp.exe'), '--show=False', '--landmarks=False', '--model_path=./models',
                f'--cam_res={width}x{height}', '--expr_mode=2', f'--camera={camera}', '--camera_cap=0',
                f'--cam_fps={fps}', f'--fps_limit={fps}', '--use_opencl=False', '--cam_api=0']
        try:
            self._process = subprocess.Popen(args, cwd=str(root), stdin=subprocess.DEVNULL,
                                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except Exception:
            sock.close()
            raise
        self._folder, self._camera, self._target_fps = str(root), camera, fps
        self._fps = 0
        self._error = ''
        self._result = {}
        self._updated_at = 0
        self._stop.clear()
        self._thread = threading.Thread(target=self._receive, args=(sock,), name='SakuraExpressionAppReceiver', daemon=True)
        self._thread.start()
        return self.snapshot()

    def _receive(self, sock):
        try:
            sock.settimeout(.5)
            count, started = 0, time.monotonic()
            while not self._stop.is_set():
                if self._process and self._process.poll() is not None:
                    self._error = f'ExpressionApp exited with code {self._process.returncode}. Check its tracker folder, RTX driver, and camera index.'
                    break
                try:
                    packet, _ = sock.recvfrom(65536)
                except socket.timeout:
                    continue
                try:
                    shapes = self.decode_packet(packet)
                    now = time.monotonic()
                    with self._lock:
                        self._result, self._updated_at = shapes, now
                        count += 1
                        if now-started >= 1:
                            self._fps = round(count/(now-started))
                            count, started = 0, now
                except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
                    continue
        finally:
            sock.close()

    def snapshot(self):
        with self._lock:
            age = time.monotonic() - self._updated_at if self._updated_at else None
            process_running = bool(self._process and self._process.poll() is None)
            return {'running': process_running and not self._error,
                    'connected': age is not None and age < 1.5,
                    'age_ms': round(age * 1000) if age is not None else None,
                    'fps': self._fps if age is not None and age < 1.5 else 0, 'target_fps': self._target_fps, 'blendshapes': expression_aliases(self._result) if age is not None and age < 1.5 else {},
                    'error': self._error, 'folder': self._folder, 'camera': self._camera}

    def stop(self):
        self._stop.set()
        process = self._process
        self._process = None
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2)
        self._thread = None
        with self._lock:
            self._result = {}
            self._updated_at = 0


tracker = ExpressionAppTracker()
