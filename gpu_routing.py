"""Independent RVC device selection; LLM placement remains in its own runtime."""
import json
import os
from pathlib import Path
import re
import subprocess
from atomic_state import atomic_text,state_lock

def selected(root):
    try:value=json.loads((Path(root)/'desktop-profile/gpu-routing.json').read_text(encoding='utf-8')).get('rvc','auto')
    except (OSError,ValueError,AttributeError):return 'auto'
    return value if isinstance(value,str) and re.fullmatch(r'auto|cpu|cuda:\d{1,2}|directml:\d{1,2}',value) else 'auto'

def devices():
    from rvc_manager import _runtime_python
    try:python=_runtime_python()
    except RuntimeError:return {'devices':[{'id':'auto','name':'Automatic'},{'id':'cpu','name':'CPU'}],'message':'Install the RVC runtime to discover GPU adapters.'}
    code="""import json
import torch
rows=[{'id':'auto','name':'Automatic'},{'id':'cpu','name':'CPU'}]
rows += [{'id':'cuda:'+str(i),'name':torch.cuda.get_device_name(i)} for i in range(torch.cuda.device_count())]
try:
 import torch_directml as d
 rows += [{'id':'directml:'+str(i),'name':d.device_name(i)} for i in range(d.device_count())]
except ImportError:pass
print(json.dumps(rows))
"""
    result=subprocess.run([str(python),'-c',code],capture_output=True,text=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    try:rows=json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError,IndexError):raise ValueError('RVC device discovery failed. Check its installed runtime.') from None
    return {'devices':rows[:32],'message':'Changes apply when the RVC worker next starts. Its GPU allocation is independent of LLM allocation.'}

def configure(root,value):
    if not isinstance(value,str) or value not in {row['id'] for row in devices()['devices']}:raise ValueError('Choose an available RVC device.')
    path=Path(root)/'desktop-profile/gpu-routing.json'
    with state_lock(path):atomic_text(path,json.dumps({'rvc':value}))
    return {'selected':value,'message':'Saved. Applies on the next RVC worker start; no active speech was interrupted.'}
