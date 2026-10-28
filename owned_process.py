"""Windows process ownership: children cannot outlive the owning application."""
import ctypes
from ctypes import wintypes
import os
import signal


class ProcessJob:
    def __init__(self):
        self.handle = None
        self.process_group = None
        if os.name != 'nt':
            return
        class Basic(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                        ('flags', wintypes.DWORD), ('min_working', ctypes.c_size_t),
                        ('max_working', ctypes.c_size_t), ('active', wintypes.DWORD),
                        ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                        ('scheduling', wintypes.DWORD)]
        class Extended(ctypes.Structure):
            _fields_ = [('basic', Basic), ('io', ctypes.c_ulonglong * 6),
                        ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                        ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Extended()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def attach_and_resume(self, process):
        if os.name != 'nt':
            # Our POSIX launchers use start_new_session; never own the parent's group.
            group = os.getpgid(process.pid)
            if group != process.pid or group == os.getpgrp():
                raise RuntimeError('Worker must start in its own process session.')
            self.process_group = group
            return
        if self.handle is None:
            return
        if not self.kernel.AssignProcessToJobObject(self.handle, wintypes.HANDLE(int(process._handle))):
            raise ctypes.WinError(ctypes.get_last_error())
        resume = ctypes.WinDLL('ntdll').NtResumeProcess
        resume.argtypes = [wintypes.HANDLE]
        resume.restype = ctypes.c_long
        if resume(wintypes.HANDLE(int(process._handle))) != 0:
            raise RuntimeError('Could not resume the owned Ollama process.')

    def attach_running_pid(self, pid):
        """Own an app-created driver before it spawns browser children. Windows only."""
        if os.name != 'nt':
            raise RuntimeError('Running process ownership requires a Windows job.')
        self.kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        self.kernel.OpenProcess.restype=wintypes.HANDLE
        handle=self.kernel.OpenProcess(0x0100|0x0001,False,pid)
        if not handle:raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.kernel.AssignProcessToJobObject(self.handle,handle):raise ctypes.WinError(ctypes.get_last_error())
        finally:self.kernel.CloseHandle(handle)

    def close(self):
        if self.process_group is not None:
            try:
                os.killpg(self.process_group, getattr(signal, 'SIGKILL', 9))
            except ProcessLookupError:
                pass
            self.process_group = None
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
