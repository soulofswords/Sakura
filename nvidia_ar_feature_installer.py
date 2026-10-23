"""Run NVIDIA's bundled AR SDK feature installer without persisting NGC keys."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from collections import deque
from pathlib import Path


REQUIRED_FEATURES = (
    "nvarfaceexpressions",
    "nvarlandmarkdetection",
    "nvarfaceboxdetection",
)


class FeatureInstaller:
    def __init__(self):
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._log: deque[str] = deque(maxlen=100)
        self._thread: threading.Thread | None = None
        self._error = ""

    def start(self, sdk_folder: str, api_key: str, *, platform: str = sys.platform,
              popen=subprocess.Popen) -> dict:
        if platform != "win32":
            raise RuntimeError("NVIDIA AR SDK feature installation is supported on Windows only.")
        if not api_key or len(api_key) > 4096 or "\x00" in api_key:
            raise ValueError("Enter a valid NVIDIA NGC API key.")
        root = Path(sdk_folder).expanduser().resolve()
        script = root / "features" / "install_feature.ps1"
        if not script.is_file():
            raise FileNotFoundError("NVIDIA's features/install_feature.ps1 was not found. Install SDK Core first.")
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                raise RuntimeError("NVIDIA feature installation is already running.")
            self._log.clear()
            self._error = ""
            env = os.environ.copy()
            env["NGC_CLI_API_KEY"] = api_key
            args = [
                "powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File", str(script),
                "-features", ",".join(REQUIRED_FEATURES),
            ]
            try:
                self._process = popen(
                    args, cwd=str(script.parent), env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                    errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError as error:
                self._error = str(error)
                raise RuntimeError(f"Could not start NVIDIA's installer: {error}") from error
            # Do not retain the API key in this object; the child needs it only while installing.
            del env["NGC_CLI_API_KEY"]
            self._thread = threading.Thread(target=self._capture_output, daemon=True)
            self._thread.start()
        return self.status()

    def _capture_output(self):
        process = self._process
        if process is None or process.stdout is None:
            return
        try:
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    with self._lock:
                        self._log.append(line[:500])
            code = process.wait()
            with self._lock:
                self._error = "" if code == 0 else f"NVIDIA installer exited with code {code}. Check NGC access and installer output."
        except Exception as error:  # Keep status visible if output capture itself fails.
            with self._lock:
                self._error = f"Could not read NVIDIA installer output: {error}"

    def status(self) -> dict:
        with self._lock:
            process = self._process
            running = process is not None and process.poll() is None
            return {
                "running": running,
                "finished": process is not None and not running,
                "returncode": process.poll() if process is not None and not running else None,
                "message": "Installing NVIDIA face-tracking features…" if running else self._error,
                "output": list(self._log),
            }


installer = FeatureInstaller()
