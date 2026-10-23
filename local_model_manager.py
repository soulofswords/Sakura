"""User-requested model downloads; existing models are retained until explicit deletion."""
import re
import threading
import requests
import hashlib
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import quote
import html

from local_model_setup import MODEL_OPTIONS
from ollama_runtime import server_for_folder, list_models


class ModelManager:
    def __init__(self):
        self.lock=threading.RLock()
        self.job={'running':False,'message':'No download running.'}

    def status(self):
        with self.lock:
            return dict(self.job)

    def catalog(self):
        return [{'id':key,'model':tag,'name':name,'ram_gb':ram,'vram_gb':vram,
                 'disk_gb':disk,'download':size} for key,tag,name,ram,vram,disk,size in MODEL_OPTIONS]

    def download(self,model,folder):
        model=str(model).strip()
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,150}(?::[A-Za-z0-9._-]{1,80})?',model):
            raise ValueError('Enter an Ollama model name such as gemma3:4b or namespace/model:tag.')
        if model.endswith('-cloud') or ':cloud' in model:
            raise ValueError('Choose a downloadable local model, rather than a cloud model.')
        with self.lock:
            if self.job['running']:
                raise ValueError('A model download is already running. Wait for it to finish.')
            url=server_for_folder(folder)
            self.job={'running':True,'model':model,'message':'Starting download…','percent':None,'vision':False}
            threading.Thread(target=self._pull,args=(url,model),daemon=True,name='SakuraModelDownload').start()
            return dict(self.job)

    def _pull(self,url,model):
        try:
            with requests.post(url+'/api/pull',json={'model':model,'stream':True},stream=True,timeout=(15,180)) as response:
                response.raise_for_status()
                success=False
                for line in response.iter_lines():
                    if not line:continue
                    import json
                    data=json.loads(line)
                    if data.get('error'):raise ValueError(data['error'])
                    total=data.get('total',0)
                    with self.lock:
                        self.job.update(message=data.get('status','Downloading…'),percent=round(data.get('completed',0)*100/total) if total else None)
                    success=success or data.get('status')=='success'
                if not success:raise ValueError('Download did not finish. Retry to resume it.')
            response=requests.post(url+'/api/show',json={'model':model},timeout=30)
            response.raise_for_status()
            vision='vision' in response.json().get('capabilities',[])
            with self.lock:
                self.job.update(vision=vision,message='Downloaded. Vision support verified. Select it and save AI settings to switch.' if vision else 'Downloaded, but vision support was not confirmed. Keep a vision model selected for camera/screen use.',percent=100)
        except Exception as error:
            with self.lock:self.job.update(message='Download failed: '+str(error),error=True)
        finally:
            with self.lock:self.job['running']=False

    def remove(self,model,folder,protected):
        with self.lock:
            if self.job['running']:raise ValueError('Wait for the download to finish before uninstalling a model.')
            normalize=lambda name:name if ':' in name else name+':latest'
            if normalize(model) in {normalize(name) for name in protected if name}:
                raise ValueError('This is your configured chat or vision model. Select another model and save AI settings first, then uninstall it.')
            if model not in {m['name'] for m in list_models(folder)}:
                raise ValueError('Choose an installed model from the refreshed list.')
            response=requests.delete(server_for_folder(folder)+'/api/delete',json={'model':model},timeout=60)
            response.raise_for_status()
            return {'ok':True,'message':'Uninstalled '+model+'. Other models were kept.'}


manager=ModelManager()


class _RegistryLinks(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.items=[]; self.link=None; self.depth=0; self.feed(text)
    def handle_starttag(self, tag, attrs):
        if tag=='a':
            self.link=[dict(attrs).get('href',''),[]]
    def handle_data(self, data):
        if self.link is not None:self.link[1].append(data)
    def handle_endtag(self, tag):
        if tag=='a' and self.link is not None:
            self.items.append((self.link[0], ' '.join(' '.join(self.link[1]).split())))
            self.link=None


def registry_search(query='', family=''):
    """Read public Ollama vision catalog; never download weights during search."""
    query=str(query).strip()[:100]; family=str(family).strip()
    if family and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,100}',family):
        raise ValueError('Choose a model family from search results.')
    url=('https://ollama.com/library/'+quote(family)+'/tags') if family else 'https://ollama.com/search'
    response=requests.get(url,params=None if family else {'q':query,'c':'vision'},timeout=20)
    response.raise_for_status()
    rows=[];seen=set()
    for href,text in _RegistryLinks(response.text).items:
        if not href.startswith('/library/'):continue
        name=href[len('/library/'):]
        if family:
            if not name.startswith(family+':') or name in seen or 'cloud' in name.lower():continue
            # Tag rows explicitly identify image input; exclude text-only variants.
            if 'Image' not in text:continue
            size=re.search(r'\b(\d+(?:\.\d+)?\s*[GMT]B)\b',text)
            rows.append({'model':name,'name':name,'download':size.group(1) if size else 'See model page','vision':True})
        else:
            if '/' in name or ':' in name or name in seen:continue
            if not re.search(r'\bvision\b',text,re.I) or re.search(r'\b(?:cloud|embedding|decision)\b',text,re.I):continue
            rows.append({'family':name,'name':name,'description':text[:350]})
        seen.add(name)
    return {'models':rows[:100], 'family':family, 'source':url}


def model_details(model,folder):
    response=requests.post(server_for_folder(folder)+'/api/show',json={'model':model},timeout=20)
    response.raise_for_status();data=response.json()
    info=data.get('model_info',{})
    return {'model':model,'vision':'vision' in data.get('capabilities',[]),
            'capabilities':data.get('capabilities',[]),'details':data.get('details',{}),
            'parameters':info.get('general.parameter_count')}


def import_gguf(manager,model,paths,folder):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,150}(?::[A-Za-z0-9._-]{1,80})?',str(model)):
        raise ValueError('Enter a local name for the imported model.')
    if not isinstance(paths,list) or not 1<=len(paths)<=32:raise ValueError('Choose GGUF weights and, for supported vision architectures, its projector.')
    files=[Path(str(p)).expanduser().resolve() for p in paths]
    if any(not p.is_file() or p.suffix.lower()!='.gguf' for p in files):raise ValueError('Every selected file must be an existing GGUF file.')
    if len({p.name for p in files})!=len(files):raise ValueError('GGUF file names must be unique.')
    url=server_for_folder(folder)
    normalize=lambda value:value if ':' in value else value+':latest'
    if normalize(model) in {normalize(m['name']) for m in list_models(folder)}:raise ValueError('Choose a new model name; an installed model already uses this name.')
    with manager.lock:
        if manager.job['running']:raise ValueError('Another model operation is running.')
        manager.job={'running':True,'model':model,'message':'Importing GGUF weights…','percent':None}
    def work():
        try:
            digests={}
            for path in files:
                with path.open('rb') as stream:
                    digest='sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()
                    stream.seek(0)
                    response=requests.post(url+'/api/blobs/'+digest,data=stream,timeout=(15,1800));response.raise_for_status()
                digests[path.name]=digest
            response=requests.post(url+'/api/create',json={'model':model,'files':digests,'stream':False},timeout=(15,1800));response.raise_for_status()
            if response.json().get('error'):raise ValueError(response.json()['error'])
            details=model_details(model,folder)
            with manager.lock:manager.job.update(vision=details['vision'],percent=100,message='Imported. '+('Vision support verified.' if details['vision'] else 'Text model imported; vision was not confirmed.'))
        except Exception as error:
            with manager.lock:manager.job.update(error=True,message='Import failed: '+str(error))
        finally:
            with manager.lock:manager.job['running']=False
    threading.Thread(target=work,daemon=True,name='SakuraGGUFImport').start()
    return manager.status()
