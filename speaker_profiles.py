"""Optional speaker comparisons are hints, never login credentials or authority."""
import json,math,os,subprocess,sys,tempfile,threading
from pathlib import Path


class SpeakerProfiles:
    def __init__(self,root):
        self.root=Path(root);self.lock=threading.Lock();self.profile_lock=threading.RLock();self.busy=False;self.error=''
    @property
    def python(self):return self.root/'runtime'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    def status(self):
        return {'ready':(self.root/'ready').is_file() and (self.root/'ready').read_text(encoding='utf-8').strip()=='speechbrain-ecapa-cpu-v2' and self.python.is_file(),'busy':self.busy,'error':self.error,'profiles':list(self._profiles()),'policy':'Speaker similarity only. Never restores owner permissions; recordings are deleted after comparison.'}
    def _profiles(self):
        from credentials import get_cloud_key
        try:data=json.loads(get_cloud_key('speaker_profiles') or '{}')
        except ValueError:data={}
        return data if isinstance(data,dict) else {}
    def _run(self,args,timeout=120):
        root=Path(__file__).resolve().parent
        bootstrap='import sys;from pathlib import Path;root=Path('+repr(str(root))+');sys.path.insert(0,str(root));\nif list(root.glob("sakura_core*.pyd")): import sakura_core\nfrom voiceprint_worker import main;main()'
        result=subprocess.run([str(self.python),'-I','-c',bootstrap,'--model',str(self.root/'model'),*args],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,env={**os.environ,'TORCH_FORCE_WEIGHTS_ONLY_LOAD':'1'},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode:raise ValueError('Speaker runtime failed. Check the optional installation or use a clear 3–30 second WAV recording.')
        return result.stdout
    def install(self):
        with self.lock:
            if self.busy:return self.status()
            self.busy=True;self.error=''
        def task():
            try:
                self._environment()
                commands=[['-m','pip','install','--disable-pip-version-check','torch==2.8.0','torchaudio==2.8.0','--index-url','https://download.pytorch.org/whl/cpu'],
                          ['-m','pip','install','--disable-pip-version-check','speechbrain==1.0.3','huggingface-hub==0.25.2','soundfile==0.13.1']]
                for args in commands:
                    result=subprocess.run([str(self.python),*args],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1800,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    if result.returncode:raise ValueError('Optional speaker dependencies could not be installed. Existing Sakura dependencies were not changed.')
                if 'SAKURA_READY' not in self._run([],600):raise ValueError('The speaker model did not report readiness.')
                from atomic_state import atomic_text
                atomic_text(self.root/'ready','speechbrain-ecapa-cpu-v2')
            except Exception as error:self.error=str(error)[:300]
            finally:self.busy=False
        threading.Thread(target=task,daemon=True,name='SakuraSpeakerSetup').start();return self.status()
    def _environment(self):
        """Installed Windows builds use embedded Python, which has no ensurepip/venv."""
        base=Path(sys.base_prefix);settings=list(base.glob('python*._pth'))
        if os.name!='nt' or not settings:
            import venv
            venv.EnvBuilder(with_pip=True).create(self.root/'runtime');return
        import hashlib,shutil,zipfile,requests
        from urllib.parse import urlsplit
        destination=self.python.parent;destination.mkdir(parents=True,exist_ok=True)
        for source in base.iterdir():
            if source.is_file() and (source.name=='python.exe' or source.suffix.lower() in ('.dll','.pyd') or (source.name.startswith('python') and source.suffix=='.zip')):
                shutil.copy2(source,destination/source.name)
        (destination/settings[0].name).write_text('python'+str(sys.version_info.major)+str(sys.version_info.minor)+'.zip\n.\nLib/site-packages\nimport site\n',encoding='utf-8')
        # A pinned pure-Python wheel bootstraps pip without running a downloaded script.
        with requests.Session() as session:
            session.trust_env=False
            response=session.get('https://pypi.org/pypi/pip/25.0.1/json',timeout=30);response.raise_for_status()
            artifact=next(x for x in response.json()['urls'] if x['filename']=='pip-25.0.1-py3-none-any.whl')
            if urlsplit(artifact['url']).hostname!='files.pythonhosted.org':raise ValueError('Unexpected pip download host.')
            with session.get(artifact['url'],stream=True,allow_redirects=False,timeout=(15,120)) as reply:
                reply.raise_for_status();data=bytearray()
                for chunk in reply.iter_content(65536):
                    data.extend(chunk)
                    if len(data)>5_000_000:raise ValueError('Pip bootstrap exceeds its size limit.')
            if hashlib.sha256(data).hexdigest()!=artifact['digests']['sha256']:raise ValueError('Pip bootstrap checksum mismatch.')
        import io
        packages=destination/'Lib'/'site-packages';packages.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(data)) as wheel:
            if any(Path(x.filename).is_absolute() or '..' in Path(x.filename).parts or ':' in x.filename or '\\' in x.filename for x in wheel.infolist()):raise ValueError('Unsafe pip wheel path.')
            wheel.extractall(packages)
    def vector(self,audio):
        if not self.status()['ready']:raise ValueError('Download the optional speaker runtime first.')
        if not isinstance(audio,bytes) or not 44<=len(audio)<=5_000_000 or not audio.startswith(b'RIFF'):raise ValueError('Use a WAV recording under 5 MB.')
        with self.lock,tempfile.TemporaryDirectory(prefix='sakura-speaker-') as temporary:
            path=Path(temporary)/'voice.wav';path.write_bytes(audio);output=self._run(['--audio',str(path)])
        line=next((line for line in output.splitlines() if line.startswith('SAKURA_VECTOR:')),None)
        if not line:raise ValueError('The speaker encoder returned no vector.')
        values=json.loads(line.removeprefix('SAKURA_VECTOR:'))
        if not isinstance(values,list) or not 32<=len(values)<=4096 or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in values):raise ValueError('Invalid speaker embedding.')
        norm=math.sqrt(sum(x*x for x in values))
        if not norm:raise ValueError('Empty speaker embedding.')
        return [x/norm for x in values]
    def enroll(self,name,audio):
        if not isinstance(name,str) or not 1<=len(name.strip())<=40:raise ValueError('Use a speaker label of up to 40 characters.')
        vector=self.vector(audio);name=name.strip()
        from credentials import set_cloud_key
        with self.profile_lock:
            profiles=self._profiles()
            if len(profiles)>=5 and name not in profiles:raise ValueError('Speaker profile limit is five.')
            profiles[name]=vector;set_cloud_key('speaker_profiles',json.dumps(profiles))
        return {'ok':True,'label':name}
    def identify(self,audio):
        vector=self.vector(audio);scores=[]
        for name,value in self._profiles().items():
            if len(value)==len(vector):scores.append((sum(a*b for a,b in zip(value,vector)),name))
        score,name=max(scores,default=(0,None))
        return {'label':name if score>=.7 else None,'similarity':score,'threshold':.7,'authority':'none','warning':'Experimental similarity, not proof of identity; no owner access is granted.'}
    def forget(self,name):
        from credentials import set_cloud_key
        with self.profile_lock:
            profiles=self._profiles();profiles.pop(name,None);set_cloud_key('speaker_profiles',json.dumps(profiles))
        return {'ok':True}
    def rename(self,name,new_name):
        if not isinstance(new_name,str) or not 1<=len(new_name.strip())<=40:raise ValueError('Use a speaker label of up to 40 characters.')
        new_name=new_name.strip()
        from credentials import set_cloud_key
        with self.profile_lock:
            profiles=self._profiles()
            if name not in profiles:raise ValueError('Speaker profile not found.')
            if new_name!=name and new_name in profiles:raise ValueError('That speaker name is already used.')
            profiles[new_name]=profiles.pop(name);set_cloud_key('speaker_profiles',json.dumps(profiles))
        return {'ok':True,'label':new_name}


def accepts_microphone(audio):
    """Enrolled-speaker filter for commands, never a permissions grant."""
    profiles=SpeakerProfiles(Path(__file__).resolve().parent/'desktop-profile'/'voiceprint')
    if not profiles._profiles():return True
    try:return profiles.identify(audio).get('label') is not None
    except Exception:return False
