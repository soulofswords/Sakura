"""Local system measurements and fixed Windows audio operations; no generated shell code."""
import ctypes
import os
import platform
import shutil
import threading
import time
import uuid
from pathlib import Path


def system_status():
    result={'platform':platform.system(),'logical_cpus':os.cpu_count(),'architecture':platform.machine(),'sampled_at':time.time()}
    if os.name=='nt':
        import sys
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
                result['cpu_name']=winreg.QueryValueEx(key,'ProcessorNameString')[0].strip()
        except OSError:
            pass
        version=sys.getwindowsversion()
        name='Windows 11' if version.major==10 and version.build>=22000 else f'Windows {version.major}'
        result['os']=f'{name} (build {version.build})'
        from ctypes import wintypes as w
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        class Memory(ctypes.Structure):
            _fields_=[('length',w.DWORD),('load',w.DWORD),*[(name,ctypes.c_ulonglong) for name in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]]
        memory=Memory();memory.length=ctypes.sizeof(memory)
        if not kernel.GlobalMemoryStatusEx(ctypes.byref(memory)):raise ctypes.WinError(ctypes.get_last_error())
        result['ram']={'total_bytes':memory.total,'used_bytes':memory.total-memory.available,'percent':round((memory.total-memory.available)/memory.total*100,1)}
        class Power(ctypes.Structure):
            _fields_=[('ac',w.BYTE),('flags',w.BYTE),('percent',w.BYTE),('reserved',w.BYTE),('seconds',w.DWORD),('full_seconds',w.DWORD)]
        power=Power()
        if kernel.GetSystemPowerStatus(ctypes.byref(power)) and power.flags!=255 and not power.flags&128:
            result['battery']={'percent':None if power.percent==255 else power.percent,'plugged_in':None if power.ac==255 else power.ac==1}
        kernel.GetTickCount64.restype=ctypes.c_ulonglong
        result['uptime_seconds']=int(kernel.GetTickCount64()/1000)
    if os.name=='nt':
        from hardware_metrics import sample_windows
        result.update(sample_windows())
    result['sampled_at']=time.time()
    root=Path.home().anchor or '/'
    disk=shutil.disk_usage(root)
    result['disk']={'root':root,'total_bytes':disk.total,'free_bytes':disk.free}
    return result

def status_reply(data):
    parts=[]
    identity=[value for value in (data.get('cpu_name'),data.get('os')) if value]
    if identity:parts.append('System: '+', '.join(identity)+'.')
    cpu=data.get('cpu_percent')
    parts.append('CPU usage is '+str(cpu)+' percent.' if cpu is not None else 'CPU usage is unavailable from Windows.')
    if data.get('ram'):
        r=data['ram'];parts.append(f"RAM usage is {r['used_bytes']/1024**3:.1f} of {r['total_bytes']/1024**3:.1f} GB, {r['percent']} percent.")
    for gpu in data.get('gpus',[]):
        usage=gpu.get('utilization_percent')
        parts.append(gpu['name']+' usage is '+str(usage)+' percent.' if usage is not None else gpu['name']+' usage is unavailable from the driver.')
        total=gpu.get('vram_total_bytes',0);used=gpu.get('vram_used_bytes')
        if total and used is not None:parts.append(f"VRAM usage is {used/1024**3:.1f} of {total/1024**3:.1f} GB, {gpu['vram_percent']} percent.")
        elif total:parts.append(f"Dedicated VRAM capacity is {total/1024**3:.1f} GB; current usage is unavailable.")
        else:parts.append('Dedicated VRAM readings are unavailable; shared memory is not counted as dedicated VRAM.')
    if not data.get('gpus'):parts.append(data.get('gpu_status','GPU usage and VRAM readings are unavailable.'))
    if data.get('battery') and data['battery']['percent'] is not None:
        b=data['battery'];parts.append(f"Battery is {b['percent']} percent"+(' and plugged in.' if b['plugged_in'] else '.'))
    parts.append(f"The system drive has {data['disk']['free_bytes']/1024**3:.1f} GB free.")
    return ' '.join(parts)

def volume(action='get',value=None):
    if os.name!='nt':raise RuntimeError('System volume controls currently support Windows only.')
    from ctypes import wintypes as w
    class Guid(ctypes.Structure):
        _fields_=[('a',w.DWORD),('b',w.WORD),('c',w.WORD),('d',w.BYTE*8)]
        def __init__(self,text):super().__init__();ctypes.memmove(ctypes.byref(self),uuid.UUID(text).bytes_le,16)
    def method(ptr,index,restype,*types):
        table=ctypes.cast(ptr,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        return ctypes.WINFUNCTYPE(restype,ctypes.c_void_p,*types)(table[index])
    def check(code):
        if code<0:raise RuntimeError(f'Windows audio operation failed (0x{code&0xffffffff:08x}).')
    ole=ctypes.OleDLL('ole32');ole.CoInitializeEx.argtypes=[ctypes.c_void_p,w.DWORD];ole.CoInitializeEx.restype=w.LONG
    initialized=ole.CoInitializeEx(None,2);check(initialized) if initialized not in (0,1,-2147417850) else None
    pointers=[]
    try:
        enum,device,audio=ctypes.c_void_p(),ctypes.c_void_p(),ctypes.c_void_p()
        cls=Guid('BCDE0395-E52F-467C-8E3D-C4579291692E');iid=Guid('A95664D2-9614-4F35-A746-DE8DB63617E6');endpoint=Guid('5CDF2C82-841E-4546-9722-0CF74078229A')
        ole.CoCreateInstance.argtypes=[ctypes.POINTER(Guid),ctypes.c_void_p,w.DWORD,ctypes.POINTER(Guid),ctypes.POINTER(ctypes.c_void_p)];ole.CoCreateInstance.restype=w.LONG
        check(ole.CoCreateInstance(ctypes.byref(cls),None,23,ctypes.byref(iid),ctypes.byref(enum)));pointers.append(enum)
        check(method(enum,4,w.LONG,w.INT,w.INT,ctypes.POINTER(ctypes.c_void_p))(enum,0,1,ctypes.byref(device)));pointers.append(device)
        check(method(device,3,w.LONG,ctypes.POINTER(Guid),w.DWORD,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p))(device,ctypes.byref(endpoint),23,None,ctypes.byref(audio)));pointers.append(audio)
        current=ctypes.c_float();muted=w.BOOL()
        check(method(audio,9,w.LONG,ctypes.POINTER(ctypes.c_float))(audio,ctypes.byref(current)))
        check(method(audio,15,w.LONG,ctypes.POINTER(w.BOOL))(audio,ctypes.byref(muted)))
        target=None
        if action=='set':target=max(0,min(1,float(value)/100))
        elif action in ('up','down'):target=max(0,min(1,current.value+(.1 if action=='up' else -.1)))
        elif action in ('mute','unmute'):check(method(audio,14,w.LONG,w.BOOL,ctypes.c_void_p)(audio,action=='mute',None))
        elif action!='get':raise ValueError('Unknown volume operation.')
        if target is not None:check(method(audio,7,w.LONG,ctypes.c_float,ctypes.c_void_p)(audio,target,None))
        check(method(audio,9,w.LONG,ctypes.POINTER(ctypes.c_float))(audio,ctypes.byref(current)))
        check(method(audio,15,w.LONG,ctypes.POINTER(w.BOOL))(audio,ctypes.byref(muted)))
        if target is not None and abs(current.value-target)>.015:raise RuntimeError('Windows did not apply the requested volume.')
        if action in ('mute','unmute') and bool(muted.value)!=(action=='mute'):raise RuntimeError('Windows did not apply the mute change.')
        return {'percent':round(current.value*100),'muted':bool(muted.value)}
    finally:
        for pointer in reversed(pointers):method(pointer,2,w.ULONG)(pointer)
        if initialized in (0,1):ole.CoUninitialize()

def find_files(query,location):
    # Explicit user folders only. No recursive drive crawl or file modification.
    if location not in ('downloads','documents','desktop'):raise ValueError('Choose Downloads, Documents or Desktop.')
    folder=Path.home()/location.title()
    if not folder.is_dir():raise RuntimeError('That user folder is unavailable at its standard location.')
    query=str(query).strip()
    if not query or len(query)>100 or any(c in query for c in '/\\\x00'):raise ValueError('Enter a file name, not a path.')
    results=[];scanned=0
    for path in folder.iterdir():
        scanned+=1
        if scanned>5000:break
        if path.is_file() and query.casefold() in path.name.casefold():
            results.append({'name':path.name,'path':str(path)})
            if len(results)>=20:break
    return {'files':results,'folder':str(folder),'limited':scanned>5000 or len(results)>=20}
