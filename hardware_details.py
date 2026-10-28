"""Teacher hardware questions use measured counters, never a generated answer."""
import json
import math
import os
import re
import subprocess
import time

PROTECTED={'system','system idle process','registry','smss.exe','csrss.exe','wininit.exe','winlogon.exe','services.exe','lsass.exe','svchost.exe','secure system','memory compression','dwm.exe'}


def question(text):
    text=text.lower().strip().rstrip('?.!')
    if re.search(r'\b(?:close|kill|stop|terminate|end task|delete)\b',text):return None
    if re.search(r'\b(?:process(?:es)?|apps?|programs?)\b',text) and re.search(r'\b(?:usage|consuming|consumption|using|resources|high|most|top)\b',text):return 'processes'
    if re.search(r'\b(?:pc|computer|system|components?|hardware)\b',text) and re.search(r'\b(?:temp(?:erature)?|watts?|wattage|power|usage)\b',text):return 'all'
    components={ {'processor':'cpu','graphics card':'gpu','memory':'ram','vram':'gpu'}.get(value,value) for value in re.findall(r'\b(cpu|processor|gpu|graphics card|ram|memory|vram)\b',text)}
    if len(components)>1 and re.search(r'\b(?:temp(?:erature)?|watts?|wattage|power|usage|used|using)\b',text):return 'all'
    component=re.search(r'\b(cpu|processor|gpu|graphics card|ram|memory|vram)\b',text)
    if component and re.search(r'\b(?:temp(?:erature)?|watts?|wattage|power|usage|using|used|consum\w*)\b',text):
        return {'processor':'cpu','graphics card':'gpu','memory':'ram','vram':'gpu'}.get(component[0],component[0])
    return None


def cpu_sensors():
    """Read optional Libre/OpenHardwareMonitor WMI; never installs a driver."""
    if os.name!='nt':return []
    script="$ErrorActionPreference='Stop'; $v=@(); foreach($ns in @('root/LibreHardwareMonitor','root/OpenHardwareMonitor')) { try { $v=@(Get-CimInstance -Namespace $ns -ClassName Sensor -ErrorAction Stop | Where-Object { $_.SensorType -in @('Temperature','Power') -and $_.Parent -match '(intelcpu|amdcpu|/cpu)' } | Select-Object Name,SensorType,Value); if($v.Count){break} } catch {} }; ConvertTo-Json -InputObject $v -Compress"
    try:
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,timeout=5,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode or len(result.stdout)>64000:return []
        rows=json.loads(result.stdout or '[]');rows=rows if isinstance(rows,list) else [rows]
        return [{'name':str(row['Name'])[:100],'type':row['SensorType'],'value':round(float(row['Value']),1),'source':'Hardware monitor WMI'} for row in rows if row.get('SensorType') in ('Temperature','Power') and isinstance(row.get('Value'),(int,float)) and math.isfinite(row['Value']) and 0<=row['Value']<2000]
    except (OSError,ValueError,subprocess.TimeoutExpired):return []


def process_usage():
    import psutil
    rows=[];total=psutil.virtual_memory().total;cpus=psutil.cpu_count() or 1
    for process in psutil.process_iter(['pid','name','memory_info','username']):
        try:
            data=process.info;name=data.get('name') or 'Unknown'
            if data['pid']<=4 or name.lower() in PROTECTED or not data.get('username'):continue
            # Hide OS service accounts; no executable paths, command lines or env.
            user=data['username'].lower()
            if user.endswith(('\\system','\\local service','\\network service')):continue
            process.cpu_percent(None);rows.append((process,data))
        except (psutil.Error,OSError):continue
    time.sleep(.2)
    output=[]
    for process,data in rows[:1024]:
        try:
            rss=process.memory_info().rss
            output.append({'pid':data['pid'],'name':data['name'],'cpu_percent':round(min(100,process.cpu_percent(None)/cpus),1),'ram_bytes':rss,'ram_percent':round(rss/total*100,1)})
        except (psutil.Error,OSError):continue
    return {'top_cpu':sorted(output,key=lambda row:row['cpu_percent'],reverse=True)[:8],
            'top_ram':sorted(output,key=lambda row:row['ram_bytes'],reverse=True)[:8],
            'sampled_at':time.time(),'source':'psutil; CPU normalized to whole PC','protected_processes_excluded':True}


def answer(text,cfg):
    kind=question(text)
    if not kind:return None
    if cfg.get('conversation_mode')!='teacher':
        from conversation_modes import teacher_prompt
        return {'reply':teacher_prompt(),'mode_required':'teacher','mode_guide':'teacher'}
    if not cfg.get('computer_control_enabled'):return {'reply':'Enable Computer access in Settings → Theme first. Choose Restricted for hardware readings or Full for process usage.'}
    if kind=='all':
        readings=[answer(prompt,cfg) for prompt in ('cpu temperature and watts','gpu temperature and watts','how much ram is being used')]
        return {'reply':' '.join(reading['reply'] for reading in readings)+' Motherboard, disk and PSU temperature/power readings are not exposed by this integration. GPU board power is not the whole PC power draw.',
                'hardware':{key:reading['hardware'] for key,reading in zip(('cpu','gpu','ram'),readings)}}
    if kind=='processes':
        if cfg.get('computer_access_level','restricted')!='full':return {'reply':'Process inspection needs Full access. Open Settings → Theme → Computer access and select Full. No process was inspected.'}
        data=process_usage()
        cpu='; '.join(f"{r['name']} (PID {r['pid']}): {r['cpu_percent']}% CPU" for r in data['top_cpu']) or 'No accessible user processes.'
        ram='; '.join(f"{r['name']} (PID {r['pid']}): {r['ram_bytes']/1024**3:.2f} GB" for r in data['top_ram']) or 'No accessible user processes.'
        return {'reply':'Highest CPU usage: '+cpu+'. Highest RAM usage: '+ram+'. Windows-critical/system processes are excluded. Nothing was stopped.','hardware':data}
    from system_tools import system_status
    data=system_status();parts=[]
    if kind=='cpu':
        cpu=data.get('cpu_percent');parts.append('CPU usage: '+str(cpu)+'%.' if cpu is not None else 'CPU usage is unavailable.')
        requested=bool(re.search(r'\b(?:temp(?:erature)?|watts?|wattage|power)\b',text,re.I))
        sensors=cpu_sensors() if requested else [];data['cpu_sensors']=sensors
        for sensor in sensors:parts.append(f"{sensor['name']}: {sensor['value']}"+('°C.' if sensor['type']=='Temperature' else ' W.'))
        for type,label in [('Temperature','temperature'),('Power','power draw')]:
            if requested and not any(s['type']==type for s in sensors):parts.append('CPU '+label+' is unavailable: Windows does not expose that sensor here. A running LibreHardwareMonitor/OpenHardwareMonitor with WMI enabled can provide it.')
    elif kind=='ram':
        ram=data.get('ram')
        parts.append(f"RAM: {ram['used_bytes']/1024**3:.1f} of {ram['total_bytes']/1024**3:.1f} GB in use ({ram['percent']}%)." if ram else 'RAM readings are unavailable.')
        if re.search(r'\b(?:temp(?:erature)?|watts?|wattage|power)\b',text,re.I):parts.append('RAM module temperature and wattage are unavailable unless exposed by a supported sensor.')
    else:
        for gpu in data.get('gpus',[]):
            parts.append(gpu['name']+': '+', '.join(label+': '+(str(gpu[key])+unit if gpu.get(key) is not None else 'unavailable') for key,label,unit in [('utilization_percent','usage','%'),('temperature_c','temperature','°C'),('power_watts','power',' W')])+'.')
            if gpu.get('vram_used_bytes') is not None:parts.append(f"VRAM: {gpu['vram_used_bytes']/1024**3:.1f} / {gpu['vram_total_bytes']/1024**3:.1f} GB.")
        if not parts:parts.append('GPU readings are unavailable from the installed driver.')
    return {'reply':' '.join(parts),'hardware':data}
