"""Hardware detection for Sakura's GPU-dependent subsystems.

The app must run unchanged on machines with NVIDIA, AMD or Intel GPUs —
and on machines with none. This module classifies the GPU vendor so each
subsystem can pick the right backend:

  - Ollama: CUDA runners ship for NVIDIA; AMD/Intel use the bundled Vulkan
    runner; native macOS Ollama uses Metal on Apple Silicon.
  - RVC voice conversion: CUDA torch on NVIDIA; torch-directml on AMD
    (installed by setup-rvc-amd.ps1); the optional Mac RVC runtime uses CPU.
  - Speech-to-text: faster-whisper runs on CPU everywhere (config default).

Detection runs at most once per process and never raises: a broken or
missing query falls back to 'cpu', which every subsystem handles.
"""
import functools
import os
import subprocess
import sys
import platform


def _creation_flags():
    return 0x08000000 if os.name == 'nt' else 0  # CREATE_NO_WINDOW


def _video_controller_names():
    """GPU names, cheapest and least invasive first: the Win32 display
    enumeration API (no subprocess, instant), then PowerShell CIM (wmic is
    removed on the newest Windows 11 builds), then wmic."""
    names = _display_adapter_names()
    if names:
        return names
    commands = (
        ['powershell', '-NoProfile', '-Command',
         '(Get-CimInstance Win32_VideoController).Name'],
        ['wmic', 'path', 'win32_VideoController', 'get', 'name'],
    )
    for command in commands:
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=15, creationflags=_creation_flags())
            found = [line.strip() for line in (result.stdout or '').splitlines()
                     if line.strip() and line.strip().lower() != 'name']
            if found:
                return found
        except Exception:
            continue
    return []


def _display_adapter_names():
    """Adapter names via EnumDisplayDevices. Covers virtual adapters and
    every active GPU; returns [] off-Windows or on any failure."""
    try:
        import ctypes

        class DISPLAY_DEVICEW(ctypes.Structure):
            _fields_ = [
                ('cb', ctypes.c_ulong),
                ('DeviceName', ctypes.c_wchar * 32),
                ('DeviceString', ctypes.c_wchar * 128),
                ('StateFlags', ctypes.c_ulong),
                ('DeviceID', ctypes.c_wchar * 128),
                ('DeviceKey', ctypes.c_wchar * 128),
            ]

        user32 = ctypes.windll.user32
        names = []
        seen = set()
        device = DISPLAY_DEVICEW()
        index = 0
        while True:
            device.cb = ctypes.sizeof(device)
            if not user32.EnumDisplayDevicesW(None, index, ctypes.byref(device), 0):
                break
            # The API repeats adapters across desktops; keep first sightings.
            if device.DeviceString and device.DeviceString not in seen:
                seen.add(device.DeviceString)
                names.append(device.DeviceString)
            index += 1
        return names
    except Exception:
        return []


def _classify(names):
    for name in names:
        if 'nvidia' in name.lower():
            return 'nvidia'
    for name in names:
        lowered = name.lower()
        if 'radeon' in lowered or 'amd' in lowered or lowered.startswith('ati'):
            return 'amd'
    for name in names:
        if 'intel' in name.lower():
            return 'intel'
    return 'cpu'


@functools.lru_cache(maxsize=1)
def detect_gpu():
    """Return {'vendor': 'nvidia'|'amd'|'intel'|'apple'|'cpu', 'names': [...]}.

    A laptop with both NVIDIA and AMD chips reports 'nvidia' — CUDA is the
    backend every subsystem prefers, and it wins Ollama's own priority too.
    """
    if sys.platform == 'darwin':
        return {'vendor': 'apple' if platform.machine().lower() == 'arm64' else 'cpu',
                'names': ['Apple Silicon (Metal)'] if platform.machine().lower() == 'arm64' else []}
    names = _video_controller_names()
    return {'vendor': _classify(names), 'names': names}


def pick_torch_device(cuda_available, directml_factory):
    """Choose the torch device for a service, without importing torch here.

    cuda_available:   the caller passes torch.cuda.is_available().
    directml_factory: callable returning a working torch-directml device
                      object (the AMD path), or None when the package is
                      absent. The factory must verify the device itself
                      (e.g. run a trivial tensor op) and raise if it does
                      not work, so a broken install falls back to CPU
                      instead of taking the service down.

    Returns (device, is_directml). NVIDIA keeps the classic 'cuda:0'
    string; DirectML returns the torch.device object its backend needs.
    """
    try:
        if cuda_available:
            return 'cuda:0', False
    except Exception:
        pass
    if directml_factory is not None:
        try:
            return directml_factory(), True
        except Exception:
            pass
    return 'cpu:0', False
