"""Sakura-owned GGUF inference, model downloads and chat for Agent mode.

Uses a private llama.cpp worker. No Ollama or LM Studio service is required.
"""
import atexit
import copy
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import re
import secrets
import shutil
import socket
import sys
import subprocess
import tempfile
import threading
import time
from urllib.parse import quote
import zipfile

import requests
from config import BASE_DIR
from owned_process import ProcessJob
from inference_engines import install as install_engine, colibri_model

RELEASE='b11899'
RUNTIME_URL='https://github.com/ggml-org/llama.cpp/releases/download/'+RELEASE+'/llama-'+RELEASE+'-bin-win-vulkan-x64.zip'
RUNTIME_SHA='abce1ade0ef7701aebb9e6ec35def26cd2c8920cfb8e344071f51b3f4867ee0a'
REPO=re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*')


class LocalAI:
    def devices(self,backend='vulkan'):
        if backend not in ('vulkan','cuda'):raise ValueError('Choose Vulkan or CUDA for device discovery.')
        binary=self.root/('runtime-cuda' if backend=='cuda' else 'runtime-vulkan')/'llama-server.exe'
        if backend=='vulkan' and not binary.is_file():binary=self.root/'runtime/llama-server.exe'
        if not binary.is_file():return {'devices':[],'message':'Install this inference runtime first.'}
        result=subprocess.run([str(binary),'--list-devices'],capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        rows=[]
        for line in (result.stdout+'\n'+result.stderr).splitlines():
            match=re.match(r'\s*((?:Vulkan|CUDA)\d+)\s*:\s*(.{1,240})',line)
            if match and match[1].lower().startswith(backend):rows.append({'id':match[1],'name':match[2]})
        return {'devices':rows[:16],'message':'Select devices independently from the RVC worker. VRAM is not pooled across engines.'}

    def __init__(self,root=None):
        self.root=Path(root or BASE_DIR/'desktop-profile'/'agent-local-ai');self.lock=threading.RLock();self.generation_lock=threading.Lock()
        self.worker=None;self.owner=None;self.port=None;self.key='';self.loaded=None;self.selection_lock=threading.RLock()
        self.job={'running':False,'message':'Ready','percent':None};self.job_thread=None
        try:self.models=json.loads((self.root/'models.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):self.models={}
        if not isinstance(self.models,dict):self.models={}
        atexit.register(self._shutdown)

    def save(self):
        self.root.mkdir(parents=True,exist_ok=True);temp=self.root/'models.tmp'
        temp.write_text(json.dumps(self.models,ensure_ascii=False),encoding='utf-8');temp.replace(self.root/'models.json')

    def companion_models(self):
        with self.lock:
            return [{'name':'sakura-native:'+item['id'],'label':item.get('name',item['id']),
                     'engine':item.get('engine','llama.cpp'),'size':item.get('bytes',0)}
                    for item in self.models.values()
                    if not item.get('projector') and item.get('id') and item.get('path') and Path(item['path']).exists()]

    def status(self):
        with self.lock:
            alive=self.worker is not None and self.worker.poll() is None
            return {'models':list(copy.deepcopy(self.models).values()),'loaded':self.loaded if alive else None,
                    'runtime_installed':any((self.root/x/'llama-server.exe').is_file() for x in ('runtime','runtime-cuda','runtime-vulkan')),'job':copy.deepcopy(self.job),
                    'engine':getattr(self,'loaded_engine','llama.cpp'),'backend':getattr(self,'loaded_backend',None),
                    'runtimes':{'cuda':(self.root/'runtime-cuda/llama-server.exe').is_file(),'vulkan':(self.root/'runtime-vulkan/llama-server.exe').is_file() or (self.root/'runtime/llama-server.exe').is_file(),'colibri':(self.root/'colibri-runtime/coli').is_file()},
                    'external_app_required':False}

    def background(self,message,function):
        with self.lock:
            if self.job['running']:raise ValueError('Wait for the current model operation to finish.')
            self.job={'running':True,'message':message,'percent':None}
        def work():
            try:
                function()
                with self.lock:self.job.update(message='Completed',percent=100)
            except Exception as error:
                with self.lock:self.job.update(message=str(error)[:500] if isinstance(error,ValueError) else 'Model operation failed. Check disk space and network, then retry.',error=True)
            finally:
                with self.lock:self.job['running']=False
        self.job_thread=threading.Thread(target=work,daemon=True,name='SakuraLocalAI');self.job_thread.start();return self.status()

    def install_runtime(self,backend='vulkan',engine='llama.cpp'):
        if os.name!='nt':raise ValueError('The managed runtime installer currently supports Windows x64.')
        if backend not in ('cuda','vulkan') or engine not in ('llama.cpp','colibri'):raise ValueError('Choose a supported inference engine and accelerator.')
        if engine=='colibri' and backend!='vulkan':raise ValueError('Qwen3.8 currently uses Vulkan on Windows; its CUDA binary is not included in the upstream release.')
        def install():
            with self.lock:
                if self.worker and self.worker.poll() is None:raise ValueError('Unload the model before updating its runtime.')
            def progress(value):
                with self.lock:self.job['percent']=value
            install_engine(self.root,engine,backend,progress)
        return self.background('Installing '+engine+' '+backend+' runtime (weights are separate)…',install)

    def import_colibri(self,path,name=''):
        folder,size,vision=colibri_model(path)
        identifier=hashlib.sha256(('colibri:'+str(folder)).encode()).hexdigest()[:24]
        with self.lock:
            if self.job['running']:raise ValueError('Wait for the current model operation to finish.')
            self.models[identifier]={'id':identifier,'name':str(name or ('Qwen3.6-35B-A3B' if (folder/'qwen36_meta.json').is_file() else 'Qwen3.8-Flash-Next'))[:180],'path':str(folder),'bytes':size,'projector':False,'owned':False,'engine':'colibri','vision':vision}
            self.save()
        return self.status()

    def inspect_folder(self,path):
        from model_inspection import inspect_folder
        result=inspect_folder(path)
        with self.lock:
            known={str(Path(item['path']).resolve()):item['name'] for item in self.models.values()}
        for row in result['models']:
            if row['path'] in known:row['name']=known[row['path']]
        return result

    def import_detected(self,path):
        from model_inspection import inspect_model
        item=inspect_model(path)
        if not item['can_add']:raise ValueError(item.get('message','This model is not compatible.'))
        with self.lock:
            if any(str(Path(row['path']).resolve())==item['path'] for row in self.models.values()):return self.status()
        if item['engine']=='colibri':return self.import_colibri(path,item['name'])
        return self.import_file(path,item['name'],item['projector'])

    @staticmethod
    def search(query):
        if not isinstance(query,str) or not 1<=len(query.strip())<=100:raise ValueError('Enter a model name.')
        r=requests.get('https://huggingface.co/api/models',params={'search':query.strip(),'filter':'gguf','limit':15,'sort':'downloads','direction':-1},timeout=25);r.raise_for_status()
        return {'models':[{'repo':x['id'],'downloads':x.get('downloads',0),'likes':x.get('likes',0)} for x in r.json() if REPO.fullmatch(x.get('id',''))]}

    @staticmethod
    def files(repo):
        if not isinstance(repo,str) or not REPO.fullmatch(repo):raise ValueError('Choose a model repository from search.')
        r=requests.get('https://huggingface.co/api/models/'+repo,params={'blobs':'true'},timeout=30);r.raise_for_status();data=r.json()
        commit=data.get('sha','')
        if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('Model repository revision could not be verified.')
        rows=[]
        for item in data.get('siblings',[]):
            name=item.get('rfilename','');lfs=item.get('lfs') or {};sha=lfs.get('sha256','');size=lfs.get('size',item.get('size',0))
            if name.lower().endswith('.gguf') and re.fullmatch('[a-f0-9]{64}',sha) and isinstance(size,int) and size>0:
                rows.append({'file':name,'sha256':sha,'bytes':size,'projector':'mmproj' in name.lower(),'split':bool(re.search(r'-\d{5}-of-\d{5}',name))})
        return {'repo':repo,'revision':commit,'files':rows,'license':(data.get('cardData') or {}).get('license','See model repository')}

    def download(self,repo,filename):
        detail=self.files(repo);entry=next((x for x in detail['files'] if x['file']==filename),None)
        if not entry:raise ValueError('Choose a GGUF file listed by the repository.')
        if entry['split']:raise ValueError('Split GGUF sets are not supported yet. Choose a single-file quantization.')
        identifier=entry['sha256'][:24]
        if identifier in self.models:raise ValueError('This file is already installed.')
        def transfer():
            folder=self.root/'models';folder.mkdir(parents=True,exist_ok=True)
            if shutil.disk_usage(folder).free<entry['bytes']+512*1024*1024:raise ValueError('Not enough free disk space for this model.')
            partial=folder/(identifier+'.part');target=folder/(identifier+'.gguf')
            url='https://huggingface.co/'+repo+'/resolve/'+detail['revision']+'/'+quote(filename,safe='/')
            start=partial.stat().st_size if partial.exists() else 0
            if start>entry['bytes']:partial.unlink();start=0
            with requests.get(url,headers={'Range':f'bytes={start}-'} if start else {},stream=True,timeout=(15,120)) as response:
                response.raise_for_status()
                if response.status_code!=206:start=0
                elif not response.headers.get('Content-Range','').startswith(f'bytes {start}-'):raise ValueError('Server returned an invalid resumed range.')
                total=start
                with partial.open('ab' if start else 'wb') as output:
                    for chunk in response.iter_content(1024*1024):
                        total+=len(chunk)
                        if total>entry['bytes']:raise ValueError('Model download exceeded its declared size.')
                        output.write(chunk)
                        with self.lock:self.job['percent']=round(total*100/entry['bytes'],1)
            with partial.open('rb') as source:sha=hashlib.file_digest(source,'sha256').hexdigest()
            if total!=entry['bytes'] or sha!=entry['sha256']:partial.unlink(missing_ok=True);raise ValueError('Model checksum failed. Nothing was installed.')
            with partial.open('rb') as source:
                if source.read(4)!=b'GGUF':raise ValueError('The downloaded file is not GGUF.')
            partial.replace(target)
            with self.lock:
                self.models[identifier]={'id':identifier,'name':repo+' / '+filename,'path':str(target),'bytes':total,'projector':entry['projector'],'owned':True,'sha256':sha};self.save()
        return self.background('Downloading '+filename,transfer)

    def import_file(self,path,name='',projector=False):
        source=Path(str(path)).expanduser().resolve(strict=True)
        if not source.is_file() or source.is_symlink():raise ValueError('Choose an existing GGUF weights file.')
        with source.open('rb') as file:
            if file.read(4)!=b'GGUF':raise ValueError('The selected file is not GGUF weights.')
        if type(projector) is not bool:raise ValueError('Projector must be true or false.')
        # Register in place: large weights are never duplicated just to add a card.
        identifier=hashlib.sha256(str(source).encode()).hexdigest()[:24]
        with self.lock:
            if self.job['running']:raise ValueError('Wait for the current model operation to finish before importing.')
            self.models[identifier]={'id':identifier,'name':str(name or source.name)[:180],'path':str(source),'bytes':source.stat().st_size,'projector':projector,'owned':False};self.save()
        return self.status()

    def remove(self,identifier,delete=False):
        with self.lock:
            if self.job['running']:raise ValueError('Wait for the model operation to finish.')
            if identifier==self.loaded or identifier==getattr(self,'loaded_projector',None):raise ValueError('Unload this model before removing its weights or projector.')
            entry=self.models.get(identifier)
            if not entry:raise ValueError('Model not found.')
            if delete:
                path=Path(entry['path']).resolve()
                if not entry.get('owned') or not path.is_relative_to((self.root/'models').resolve()):raise ValueError('Imported files stay in their original folder. Only Sakura-downloaded files can be deleted here.')
                path.unlink(missing_ok=True)
            self.models.pop(identifier);self.save()
        return self.status()

    def load(self,identifier,projector='',context=4096,gpu_layers=0,backend='auto',devices=None):
        if type(context) is not int or not 512<=context<=32768:raise ValueError('Context must be 512–32768 tokens.')
        if type(gpu_layers) is not int or not 0<=gpu_layers<=999:raise ValueError('GPU layers must be 0–999; use 0 for CPU.')
        with self.lock:entry=copy.deepcopy(self.models.get(identifier));vision=copy.deepcopy(self.models.get(projector)) if projector else None
        if not entry or entry['projector']:raise ValueError('Choose an installed language model.')
        if backend not in ('auto','cuda','vulkan','cpu'):raise ValueError('Choose Auto, CUDA, Vulkan or CPU.')
        engine=entry.get('engine','llama.cpp')
        if engine=='colibri':
            colibri_model(entry['path'])
            if projector:raise ValueError('Colibri uses its model folder vision encoder, not a GGUF projector.')
            if backend=='cuda':raise ValueError('Use Auto or Vulkan for the managed Colibri runtime. Qwen3.6 CUDA needs full expert residency; this launcher uses bounded caching. Qwen3.8 Windows CUDA is unavailable in v2.0.0.')
            selected='cpu' if backend=='cpu' else 'vulkan'
            binary=self.root/'colibri-runtime/coli'
        else:
            selected=('cuda' if (self.root/'runtime-cuda/llama-server.exe').is_file() else 'vulkan') if backend=='auto' else backend
            binary=self.root/('runtime-cuda' if selected=='cuda' else 'runtime-vulkan')/'llama-server.exe'
            if selected!='cuda' and not binary.is_file():binary=self.root/'runtime/llama-server.exe'
        if not binary.is_file():raise ValueError('Install the selected inference runtime first.')
        if devices is None:devices=[]
        if not isinstance(devices,list) or len(devices)>16 or any(not isinstance(d,str) for d in devices) or len(set(devices))!=len(devices):raise ValueError('Choose a list of distinct GPU devices.')
        if devices:
            if engine=='colibri' or selected=='cpu' or gpu_layers==0:raise ValueError('Explicit multi-GPU placement currently applies to GPU-offloaded llama.cpp models, not Colibri or CPU mode.')
            available={d['id'] for d in self.devices(selected)['devices']}
            if not set(devices)<=available:raise ValueError('A selected GPU is unavailable for this runtime. Refresh devices.')
        if projector and (not vision or not vision['projector']):raise ValueError('Choose an installed matching vision projector.')
        if engine!='colibri' and not Path(entry['path']).is_file():raise ValueError('Model file moved or was deleted. Import it again.')
        def launch():
            self._shutdown()
            with socket.socket() as listener:listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
            key='sakura_'+secrets.token_urlsafe(32)
            args=[str(binary),'-m',entry['path'],'--host','127.0.0.1','--port',str(port),'--api-key',key,'-c',str(context),'-ngl',str(0 if selected=='cpu' else gpu_layers),'--alias',identifier]
            if vision:args+=['--mmproj',vision['path']]
            if devices:
                args+=['--device',','.join(devices)]
                if len(devices)>1:args+=['--split-mode','layer','--tensor-split',','.join('1' for _ in devices)]
            if vision and (gpu_layers==0 or selected=='cpu'):args+=['--no-mmproj-offload']
            env=os.environ.copy()
            if engine=='colibri':
                args=[sys.executable,str(binary),'serve','--model',entry['path'],'--model-id',identifier,'--host','127.0.0.1','--port',str(port),'--api-key',key,'--ctx',str(context),'--cap','64' if (Path(entry['path'])/'qwen36_meta.json').is_file() else '8']
                env.update(COLI_VULKAN='1' if selected=='vulkan' else '0',COLI_CUDA='0')
                if (Path(entry['path'])/'qwen36_meta.json').is_file():
                    env.update(OMP_NUM_THREADS='6',COLI_VK_TIER_GB='5',COLI_NO_OMP_TUNE='1',Q36_MAX_IMAGE_TOKENS='256',COLI_VK_CHAIN_ROWS_MAX='512')
                env['PYTHONPATH']=str(binary.parent)+os.pathsep+env.get('PYTHONPATH','')
            flags=subprocess.CREATE_NO_WINDOW|0x00000004 if os.name=='nt' else 0  # CREATE_SUSPENDED
            owner=ProcessJob()
            try:
                with (self.root/'runtime.log').open('ab') as log:worker=subprocess.Popen(args,stdout=log,stderr=log,stdin=subprocess.DEVNULL,env=env,cwd=str(binary.parent),creationflags=flags,start_new_session=os.name!='nt')
                try:owner.attach_and_resume(worker)
                except Exception:worker.kill();worker.wait();raise
                with self.lock:self.worker=worker;self.owner=owner;self.port=port;self.key=key
                deadline=time.monotonic()+(900 if engine=='colibri' else 240)
                while time.monotonic()<deadline:
                    if worker.poll() is not None:raise ValueError('The model failed to load. Try fewer GPU layers or a smaller context; see the local runtime log.')
                    try:
                        if requests.get(f'http://127.0.0.1:{port}/v1/models',headers={'Authorization':'Bearer '+key},timeout=2,allow_redirects=False).status_code==200:
                            with self.lock:self.loaded=identifier;self.loaded_projector=projector or None;self.vision=bool(vision) or bool(entry.get('vision'));self.loaded_engine=engine;self.loaded_backend=selected
                            return
                    except requests.RequestException:pass
                    time.sleep(.4)
                raise ValueError('Model loading timed out; try a smaller model/context.')
            except Exception:self._shutdown();owner.close();raise
        return self.background('Loading '+entry['name'],launch)

    def unload(self):
        with self.lock:
            if self.job['running']:raise ValueError('Wait for loading or download to finish before unloading.')
        return self._shutdown()

    def _shutdown(self):
        if not self.generation_lock.acquire(blocking=False):raise ValueError('Wait for generation to finish before unloading.')
        try:
            with self.lock:
                if self.owner:self.owner.close()
                if self.worker and self.worker.poll() is None:self.worker.terminate()
                if self.worker:
                    try:self.worker.wait(timeout=5)
                    except subprocess.TimeoutExpired:self.worker.kill()
                self.worker=None;self.owner=None;self.loaded=None;self.loaded_projector=None;self.port=None;self.key='';self.loaded_backend=None
        finally:self.generation_lock.release()

    def request_model(self,identifier,messages,structured=False,planning=False):
        # One shared worker; serialize lazy model selection with generation.
        with self.selection_lock:
            if self.loaded!=identifier or not self.worker or self.worker.poll() is not None:
                self.load(identifier,context=8192,gpu_layers=999,backend='auto')
                self.job_thread.join(905)
                if self.loaded!=identifier:raise ValueError(self.job.get('message','Could not load the selected model.'))
            return self._request_raw(messages,structured=structured,planning=planning)

    def _request_raw(self,messages,structured=False,planning=False):
        if not isinstance(messages,list) or not 1<=len(messages)<=50:raise ValueError('Provide between 1 and 50 chat messages.')
        if len(json.dumps(messages))>8_000_000:raise ValueError('Chat input is too large.')
        for row in messages:
            if not isinstance(row,dict) or row.get('role') not in ('system','user','assistant') or not isinstance(row.get('content'),(str,list)):raise ValueError('Invalid chat message.')
            if isinstance(row['content'],list):
                for part in row['content']:
                    if not isinstance(part,dict):raise ValueError('Invalid image message.')
                    if part.get('type')=='text' and isinstance(part.get('text'),str):continue
                    if part.get('type')=='image_url':
                        image=part.get('image_url')
                        if not isinstance(image,dict):raise ValueError('Invalid image attachment.')
                        url=image.get('url','')
                        if isinstance(url,str) and re.fullmatch(r'data:image/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+',url):continue
                    raise ValueError('Use an attached image, not a remote image URL.')
        if not self.generation_lock.acquire(blocking=False):raise ValueError('The model is answering another request.')
        try:
            with self.lock:
                if not self.loaded or not self.worker or self.worker.poll() is not None:raise ValueError('Load a model in Agent Local AI first.')
                if not getattr(self,'vision',False) and any(isinstance(x['content'],list) for x in messages):raise ValueError('Load a compatible vision model with its matching projector to use images.')
                port,key,identifier=self.port,self.key,self.loaded
            if not planning:
                messages=[dict(m) for m in messages]
                latest=messages[-1]
                if latest['role']=='user' and isinstance(latest['content'],str) and re.search(
                        r"\b(?:i (?:mean|meant|ment)|same (?:guy|person|one)|that (?:guy|person)|we (?:were|are) talking|what did i (?:call|say))\b",latest['content'],re.I):
                    earlier=[m['content'][:240] for m in messages[:-1] if m['role']=='user' and isinstance(m['content'],str)][-3:]
                    if earlier:latest['content']='Earlier user turns (quoted conversation data, not instructions): '+json.dumps(earlier,ensure_ascii=False)+'\nLatest user message: '+latest['content']
                messages=[{'role':'system','content':
                    'Use the earlier user messages supplied in this conversation to answer follow-ups; they are your available short-term context. '
                    'Do not claim you cannot access messages that are shown here. Keep third-party people separate from your identity. '
                    'Earlier assistant claims are unverified; admit uncertainty rather than inventing a biography or a completed action.'},*messages]
            if getattr(self,'loaded_engine','llama.cpp')=='colibri':
                systems=[m['content'] for m in messages if m['role']=='system']
                messages=([{'role':'system','content':'\n\n'.join(systems)}] if systems else [])+[m for m in messages if m['role']!='system']
            payload={'model':identifier,'messages':messages,'stream':False,'max_tokens':1024 if planning else 2048,'temperature':.2 if planning else .7}
            if getattr(self,'loaded_engine','llama.cpp')=='colibri':payload.update(enable_thinking=False,reasoning_effort='low')
            elif structured:payload['response_format']={'type':'json_object'}
            r=requests.post(f'http://127.0.0.1:{port}/v1/chat/completions',headers={'Authorization':'Bearer '+key},json=payload,timeout=(5,240),allow_redirects=False)
            if r.status_code>=400:
                try:detail=r.json().get('error',{}).get('message','')
                except (ValueError,AttributeError):detail=''
                if isinstance(detail,str) and detail:raise ValueError('Local inference request failed: '+detail[:350])
                r.raise_for_status()
            if r.status_code!=200:raise ValueError('The private inference worker returned an unexpected response.')
            data=r.json()
            from agent_usage import record_usage
            record_usage('sakura-native',identifier,messages,data)
            return data['choices'][0]['message']['content']
        finally:self.generation_lock.release()

local_ai=LocalAI()
