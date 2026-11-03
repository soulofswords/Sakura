"""Primary-monitor brightness through read/write DDC/CI VCP code 0x10 on Windows."""
import ctypes
import sys
import time
from contextlib import contextmanager
from ctypes import wintypes


_IS_WINDOWS = sys.platform == 'win32'
_VCP_BRIGHTNESS = 0x10


class _PhysicalMonitor(ctypes.Structure):
    _fields_ = [('handle', wintypes.HANDLE), ('description', wintypes.WCHAR * 128)]


class _MonitorInfo(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT),
                ('rcWork', wintypes.RECT), ('dwFlags', wintypes.DWORD)]


def _error(label):
    code = ctypes.get_last_error() & 0xffffffff
    raise OSError(f'{label} failed (Windows error 0x{code:08X}).')


@contextmanager
def _primary_monitors():
    if not _IS_WINDOWS:
        raise OSError('Display brightness control is available on Windows only.')
    user = ctypes.WinDLL('user32', use_last_error=True)
    dxva = ctypes.WinDLL('dxva2', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                      ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    monitors = []

    @callback_type
    def collect(handle, _dc, _rect, _data):
        info = _MonitorInfo()
        info.cbSize = ctypes.sizeof(info)
        if user.GetMonitorInfoW(handle, ctypes.byref(info)) and info.dwFlags & 1:
            monitors.append(handle)
        return True

    if not user.EnumDisplayMonitors(None, None, collect, 0) or not monitors:
        _error('Monitor enumeration')
    count = wintypes.DWORD()
    if not dxva.GetNumberOfPhysicalMonitorsFromHMONITOR(monitors[0], ctypes.byref(count)) or not count.value:
        _error('Physical monitor discovery')
    values = (_PhysicalMonitor * count.value)()
    if not dxva.GetPhysicalMonitorsFromHMONITOR(monitors[0], count, values):
        _error('Physical monitor discovery')
    try:
        yield dxva, list(values)
    finally:
        dxva.DestroyPhysicalMonitors(count, values)


def _read_native():
    with _primary_monitors() as (dxva, monitors):
        monitor = monitors[0]
        kind = wintypes.DWORD(); current = wintypes.DWORD(); maximum = wintypes.DWORD()
        for attempt in range(5):
            if dxva.GetVCPFeatureAndVCPFeatureReply(
                    monitor.handle, _VCP_BRIGHTNESS, ctypes.byref(kind), ctypes.byref(current), ctypes.byref(maximum)):break
            if attempt<4:time.sleep(1)
        else:_error('DDC/CI brightness read')
        if maximum.value <= 0:
            raise OSError('The monitor returned an invalid DDC/CI brightness range.')
        percent = round(current.value * 100 / maximum.value)
        return {'description': monitor.description or 'Primary monitor', 'current': max(0, min(100, percent)),
                'raw_current': current.value, 'raw_maximum': maximum.value}


def _write_native(percent):
    with _primary_monitors() as (dxva, monitors):
        monitor = monitors[0]
        kind = wintypes.DWORD(); current = wintypes.DWORD(); maximum = wintypes.DWORD()
        for attempt in range(5):
            if dxva.GetVCPFeatureAndVCPFeatureReply(
                    monitor.handle, _VCP_BRIGHTNESS, ctypes.byref(kind), ctypes.byref(current), ctypes.byref(maximum)):break
            if attempt<4:time.sleep(1)
        else:_error('DDC/CI brightness read')
        raw = round(maximum.value * percent / 100)
        for attempt in range(5):
            if dxva.SetVCPFeature(monitor.handle, _VCP_BRIGHTNESS, wintypes.DWORD(raw)):break
            if attempt<4:time.sleep(1)
        else:_error('DDC/CI brightness write')
        return {'description': monitor.description or 'Primary monitor', 'current': percent,
                'raw_current': raw, 'raw_maximum': maximum.value}


def brightness(action='get', value=None):
    """Read or adjust the primary display. Callers must approval-gate writes."""
    action = str(action or 'get').casefold()
    if action == 'get':
        return _read_native()
    current = _read_native()['current'] if action in ('up', 'down') else None
    if action == 'up':
        value = current + 10
    elif action == 'down':
        value = current - 10
    elif action != 'set':
        raise ValueError('Brightness action must be get, set, up or down.')
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValueError('Choose brightness from 0 to 100 percent.') from None
    if not 0 <= value <= 100:
        raise ValueError('Choose brightness from 0 to 100 percent.')
    return _write_native(value)
