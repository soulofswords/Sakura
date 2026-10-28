"""Fresh Windows hardware counters. No model inference, shell, or extra packages."""
import ctypes
import math
import os
import re
import threading
import time
import uuid
from collections import defaultdict
_lock=threading.Lock()

def aggregate_gpu(adapters,engines,memory):
    busy=defaultdict(lambda:defaultdict(float));used={}
    for name,value in engines:
        match=re.search(r'(luid_0x[0-9a-f]+_0x[0-9a-f]+_phys_\d+)_eng_(\d+)',name,re.I)
        if match and math.isfinite(value):busy[match[1].lower()][match[2]]+=max(0,value)
    for name,value in memory:
        if math.isfinite(value) and value>=0:used[name.lower()]=int(value)
    results=[]
    for adapter in adapters:
        row=dict(adapter);key=row.pop('counter_key').lower()
        row['utilization_percent']=round(min(100,max(busy[key].values())),1) if key in busy else None
        row['vram_used_bytes']=used.get(key)
        total=row['vram_total_bytes'];usage=row['vram_used_bytes']
        row['vram_percent']=round(min(100,usage/total*100),1) if total and usage is not None else None
        row['utilization_source']='Windows busiest GPU engine'
        results.append(row)
    return results

def _adapters():
    from ctypes import wintypes as w
    class Guid(ctypes.Structure):_fields_=[('raw',w.BYTE*16)]
    class Luid(ctypes.Structure):_fields_=[('low',w.DWORD),('high',w.LONG)]
    class Desc(ctypes.Structure):
        _fields_=[('name',w.WCHAR*128),('vendor',w.UINT),('device',w.UINT),('subsystem',w.UINT),('revision',w.UINT),('video',ctypes.c_size_t),('system',ctypes.c_size_t),('shared',ctypes.c_size_t),('luid',Luid),('flags',w.UINT)]
    def method(ptr,index,restype,*args):
        table=ctypes.cast(ptr,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        return ctypes.WINFUNCTYPE(restype,ctypes.c_void_p,*args)(table[index])
    iid=Guid();ctypes.memmove(ctypes.byref(iid),uuid.UUID('770aae78-f26f-4dba-a829-253c83d1b387').bytes_le,16)
    dxgi=ctypes.WinDLL('dxgi');dxgi.CreateDXGIFactory1.argtypes=[ctypes.POINTER(Guid),ctypes.POINTER(ctypes.c_void_p)];dxgi.CreateDXGIFactory1.restype=w.LONG
    factory=ctypes.c_void_p()
    if dxgi.CreateDXGIFactory1(ctypes.byref(iid),ctypes.byref(factory))<0:return []
    rows=[]
    try:
        for index in range(16):
            adapter=ctypes.c_void_p()
            if method(factory,12,w.LONG,w.UINT,ctypes.POINTER(ctypes.c_void_p))(factory,index,ctypes.byref(adapter))<0:break
            try:
                desc=Desc()
                if method(adapter,10,w.LONG,ctypes.POINTER(Desc))(adapter,ctypes.byref(desc))<0 or desc.flags&2:continue
                rows.append({'name':desc.name,'vram_total_bytes':desc.video,'shared_memory_limit_bytes':desc.shared,
                    'counter_key':f'luid_0x{desc.luid.high&0xffffffff:08x}_0x{desc.luid.low:08x}_phys_0'})
            finally:method(adapter,2,w.ULONG)(adapter)
    finally:method(factory,2,w.ULONG)(factory)
    return rows

def _cpu_times():
    from ctypes import wintypes as w
    kernel=ctypes.WinDLL('kernel32');a,b,c=w.FILETIME(),w.FILETIME(),w.FILETIME()
    if not kernel.GetSystemTimes(ctypes.byref(a),ctypes.byref(b),ctypes.byref(c)):return None
    value=lambda t:(t.dwHighDateTime<<32)|t.dwLowDateTime
    return value(a),value(b)+value(c)

def _nvidia_devices():
    """NVML reports physical NVIDIA boards and their actual framebuffer capacity."""
    from pathlib import Path
    paths=[Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/nvml.dll',Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'NVIDIA Corporation/NVSMI/nvml.dll']
    library=next((path for path in paths if path.is_file()),None)
    if not library:return []
    api=ctypes.WinDLL(str(library));initialized=False;rows=[]
    try:
        if api.nvmlInit_v2()!=0:return []
        initialized=True
        count=ctypes.c_uint();api.nvmlDeviceGetCount_v2.argtypes=[ctypes.POINTER(ctypes.c_uint)]
        if api.nvmlDeviceGetCount_v2(ctypes.byref(count))!=0:return []
        api.nvmlDeviceGetHandleByIndex_v2.argtypes=[ctypes.c_uint,ctypes.POINTER(ctypes.c_void_p)]
        api.nvmlDeviceGetName.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_uint]
        class Memory(ctypes.Structure):_fields_=[('total',ctypes.c_ulonglong),('free',ctypes.c_ulonglong),('used',ctypes.c_ulonglong)]
        class Util(ctypes.Structure):_fields_=[('gpu',ctypes.c_uint),('memory',ctypes.c_uint)]
        api.nvmlDeviceGetMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Memory)]
        api.nvmlDeviceGetUtilizationRates.argtypes=[ctypes.c_void_p,ctypes.POINTER(Util)]
        for index in range(min(count.value,32)):
            handle=ctypes.c_void_p()
            if api.nvmlDeviceGetHandleByIndex_v2(index,ctypes.byref(handle))!=0:continue
            name=ctypes.create_string_buffer(128)
            if api.nvmlDeviceGetName(handle,name,len(name))!=0:continue
            memory,util=Memory(),Util();has_memory=api.nvmlDeviceGetMemoryInfo(handle,ctypes.byref(memory))==0
            has_util=api.nvmlDeviceGetUtilizationRates(handle,ctypes.byref(util))==0 and util.gpu<=100
            total=memory.total if has_memory else 0;used=memory.used if has_memory and memory.used<=memory.total else None
            temperature,power=ctypes.c_uint(),ctypes.c_uint()
            def sensor(function,arguments,value,scale=1):
                try:
                    fn=getattr(api,function);fn.argtypes=[ctypes.c_void_p,*([ctypes.c_uint] if len(arguments) else []),ctypes.POINTER(ctypes.c_uint)]
                    return round(value.value/scale,1) if fn(handle,*arguments,ctypes.byref(value))==0 else None
                except AttributeError:return None
            temp=sensor('nvmlDeviceGetTemperature',[0],temperature)
            watts=sensor('nvmlDeviceGetPowerUsage',[],power,1000)
            rows.append({'name':name.value.decode('utf-8',errors='replace'),'utilization_percent':util.gpu if has_util else None,
                'temperature_c':temp,'power_watts':watts,
                'vram_total_bytes':total,'vram_used_bytes':used,'vram_percent':round(used/total*100,1) if total and used is not None else None,
                'utilization_source':'NVIDIA NVML'})
    except (OSError,AttributeError):return []
    finally:
        if initialized:api.nvmlShutdown()
    return rows

def sample_windows(interval=.25):
    if os.name!='nt':return {'gpus':[],'gpu_status':'Live GPU counters currently support Windows only.'}
    from ctypes import wintypes as w
    with _lock:
        before=_cpu_times();query=ctypes.c_void_p();pdh=None;counters={};engines=[];memory=[]
        try:
            pdh=ctypes.WinDLL('pdh');handle=ctypes.c_void_p
            pdh.PdhOpenQueryW.argtypes=[w.LPCWSTR,ctypes.c_size_t,ctypes.POINTER(handle)];pdh.PdhOpenQueryW.restype=w.LONG
            pdh.PdhAddEnglishCounterW.argtypes=[handle,w.LPCWSTR,ctypes.c_size_t,ctypes.POINTER(handle)];pdh.PdhAddEnglishCounterW.restype=w.LONG
            pdh.PdhCollectQueryData.argtypes=[handle];pdh.PdhCollectQueryData.restype=w.LONG
            pdh.PdhCloseQuery.argtypes=[handle]
            pdh.PdhGetFormattedCounterArrayW.argtypes=[handle,w.DWORD,ctypes.POINTER(w.DWORD),ctypes.POINTER(w.DWORD),ctypes.c_void_p];pdh.PdhGetFormattedCounterArrayW.restype=w.LONG
            if pdh.PdhOpenQueryW(None,0,ctypes.byref(query))==0:
                for key,path in [('engines',r'\GPU Engine(*)\Utilization Percentage'),('memory',r'\GPU Adapter Memory(*)\Dedicated Usage')]:
                    counter=handle()
                    if pdh.PdhAddEnglishCounterW(query,path,0,ctypes.byref(counter))==0:counters[key]=counter
                pdh.PdhCollectQueryData(query)
        except (OSError,AttributeError):pass
        time.sleep(interval)
        after=_cpu_times();result={}
        if before and after and after[1]>before[1]:result['cpu_percent']=round(max(0,min(100,100*(1-(after[0]-before[0])/(after[1]-before[1])))),1)
        try:
            if pdh and query and counters and pdh.PdhCollectQueryData(query)==0:
                class Number(ctypes.Union):_fields_=[('value',ctypes.c_double),('large',ctypes.c_longlong)]
                class Value(ctypes.Structure):_fields_=[('status',w.DWORD),('number',Number)]
                class Item(ctypes.Structure):_fields_=[('name',w.LPWSTR),('value',Value)]
                def values(counter):
                    size,count=w.DWORD(),w.DWORD()
                    pdh.PdhGetFormattedCounterArrayW(counter,0x200,ctypes.byref(size),ctypes.byref(count),None)
                    if not 0<size.value<=16*1024*1024:return []
                    buffer=ctypes.create_string_buffer(size.value)
                    if pdh.PdhGetFormattedCounterArrayW(counter,0x200,ctypes.byref(size),ctypes.byref(count),buffer)!=0:return []
                    if count.value*ctypes.sizeof(Item)>size.value:return []
                    array=ctypes.cast(buffer,ctypes.POINTER(Item))
                    return [(array[i].name,array[i].value.number.value) for i in range(count.value) if array[i].value.status in (0,1)]
                engines=values(counters['engines']) if 'engines' in counters else []
                memory=values(counters['memory']) if 'memory' in counters else []
        except (OSError,AttributeError):pass
        finally:
            if pdh and query:pdh.PdhCloseQuery(query)
        try:adapters=_adapters()
        except (OSError,AttributeError):adapters=[]
        result['gpus']=aggregate_gpu(adapters,engines,memory)
        try:nvidia=_nvidia_devices()
        except (OSError,AttributeError):nvidia=[]
        if nvidia:result['gpus']=[g for g in result['gpus'] if 'nvidia' not in g['name'].lower()]+nvidia
        result['gpu_status']='available' if result['gpus'] else 'GPU telemetry is unavailable from the Windows driver.'
        result['sample_window_seconds']=interval
        return result
