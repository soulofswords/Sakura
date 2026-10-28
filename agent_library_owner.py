"""Fixed owner-library workflow. No credentials, paths or commands from an LLM."""
import atexit
import copy
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time

from config import BASE_DIR
from credentials import _crypt
from owned_process import ProcessJob

PINNED_FILES=('tools/agent-library-workflow.py','tools/verify-jio-publication.py','tools/sync-jio-library.py',
 'tools/sync-jio-pmx-sources.py','tools/sync-jio-live2d-sources.py','tools/prepare-jio-pmx-library.py',
 'tools/publish-model-library.py','tools/render-pmx-library-previews.cjs','tools/library-preview-server.py',
 'tools/upload-library-jio.py','tools/publish-library-jio.py','tools/jio_library_owner.py',
 'model_import.py','model_rig_validation.py','model_library_previews.py','model_library_paths.py','scenery_assets.py')


class OwnerLibrary:
    def __init__(self,base=None,enabled=lambda:True):
        self.base=Path(base or BASE_DIR);self.path=self.base/'.library-publisher.bin';self.enabled=enabled
        self.lock=threading.RLock();self.worker=None;self.owner=None;self.stop_event=threading.Event();self.thread=None
        atexit.register(self.close)

    def _read(self):
        if not self.path.is_file():return None
        try:
            data=json.loads(_crypt(self.path.read_bytes(),decrypt=True))
            if data.get('version')!=1 or not isinstance(data.get('root'),str):raise ValueError()
            root=Path(data['root']).resolve(strict=True)
            for name in PINNED_FILES:
                path=root/name
                if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=data['hashes'].get(name):raise ValueError()
            private=root.parent/'private-model-library'
            proof=json.loads(_crypt((private/'.jio-publish-proof.bin').read_bytes(),decrypt=True))
            session=json.loads(_crypt((private/'.jio-owner-session.bin').read_bytes(),decrypt=True))
            if not secrets.compare_digest(hashlib.sha256(proof['token'].encode()).hexdigest(),data['proof_hash']):raise ValueError()
            if not secrets.compare_digest(hashlib.sha256(str(session['session']['userId']).encode()).hexdigest(),data['account_hash']):raise ValueError()
            if not session['session'].get('twoFAValidated'):raise ValueError()
            return data
        except Exception:raise ValueError('Owner publisher registration changed or could not be unlocked. Re-register it on the owner PC.') from None

    def _save(self,data):
        self.path.parent.mkdir(parents=True,exist_ok=True);temporary=self.path.with_suffix('.tmp')
        temporary.write_bytes(_crypt(json.dumps(data).encode()));temporary.replace(self.path)

    def register(self,root):
        """Owner installation step only; deliberately NOT exposed by any API/tool."""
        root=Path(root).resolve(strict=True);private=root.parent/'private-model-library'
        proof=json.loads(_crypt((private/'.jio-publish-proof.bin').read_bytes(),decrypt=True))
        session=json.loads(_crypt((private/'.jio-owner-session.bin').read_bytes(),decrypt=True))
        if not session.get('session',{}).get('twoFAValidated') or len(proof.get('token',''))<40:raise ValueError('A verified owner Jio account and publisher capability are required.')
        data={'version':1,'root':str(root),'proof_hash':hashlib.sha256(proof['token'].encode()).hexdigest(),
              'account_hash':hashlib.sha256(str(session['session']['userId']).encode()).hexdigest(),
              'hashes':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in PINNED_FILES},
              'schedule':{'enabled':False,'minutes':60,'next_run':time.time()+3600}}
        with self.lock:
            try:old=json.loads(_crypt(self.path.read_bytes(),decrypt=True)) if self.path.exists() else None
            except Exception:old=None
            if old:data['schedule']=old.get('schedule',data['schedule'])
            self._save(data)
        return {'owner_available':True}

    @staticmethod
    def _busy(root):
        if os.name!='nt':return False
        import msvcrt
        for directory,name in ((directory,name) for directory in ('private-model-library-pmx','private-model-library-account2-pmx') for name in ('jio-sync.lock','jio-upload.lock')):
            path=root.parent/directory/name
            if not path.exists():continue
            with path.open('r+b') as file:
                try:msvcrt.locking(file.fileno(),msvcrt.LK_NBLCK,1)
                except OSError:return True
                else:file.seek(0);msvcrt.locking(file.fileno(),msvcrt.LK_UNLCK,1)
        return False

    def status(self):
        with self.lock:
            try:data=self._read()
            except ValueError as error:return {'owner_available':False,'registration_error':str(error)}
            if not data:return {'owner_available':False}
            root=Path(data['root']);directory=root.parent/'private-model-library-pmx';state={}
            try:state=json.loads((directory/'agent-library-status.json').read_text(encoding='utf-8'))
            except (OSError,ValueError):pass
            if not state:
                try:state=json.loads((directory/'publication-completion.json').read_text(encoding='utf-8'))
                except (OSError,ValueError):pass
            second=root.parent/'private-model-library-account2-pmx/publication-completion.json'
            try:
                additional=json.loads(second.read_text(encoding='utf-8'))
                if additional.get('state')!='complete':state=additional
            except (OSError,ValueError):pass
            running=self.worker is not None and self.worker.poll() is None
            expected=getattr(self,'last_run','')
            if expected and state.get('run_id')!=expected:
                state={'state':'starting' if running else 'interrupted','message':'Waiting for this workflow to report verified progress.' if running else 'This workflow stopped before reporting completion.'}
            if self.worker is not None and not running and self.owner:
                self.owner.close();self.owner=None
            if not running and state.get('state') in ('starting','syncing','verifying') and state.get('run_id')==getattr(self,'last_run',''):
                state={'state':'interrupted','message':'The owner workflow stopped before completion. Run again to resume verified files.'}
            busy=self._busy(root)
            if busy and not running:state={'state':'transfer_in_progress','message':'An existing owner transfer is running. No duplicate was started.'}
            allowed={key:state[key] for key in ('state','phase','message','updated_at','run_id','pmx_looks','live2d_models','sample_install_verified') if key in state}
            return {'owner_available':True,'running':running,'busy':busy,'schedule':copy.deepcopy(data['schedule']),'result':allowed}

    def start(self,approved=False):
        if approved is not True:raise ValueError('Approve the owner sync workflow first.')
        if not self.enabled():raise ValueError('Owner sync is paused in tracking-only mode.')
        with self.lock:
            data=self._read()
            if not data:raise ValueError('This installation is not the registered library publisher.')
            root=Path(data['root'])
            if (self.worker and self.worker.poll() is None) or self._busy(root):return {'started':False,'busy':True,'message':'A library transfer is already running; no duplicate was started.'}
            python=root/'venv/Scripts/python.exe'
            if not python.is_file():raise ValueError('The owner publishing Python environment is missing.')
            environment=dict(os.environ,PYTHONIOENCODING='utf-8',NODE_PATH=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'))
            run=secrets.token_hex(16);directory=root.parent/'private-model-library-pmx';directory.mkdir(exist_ok=True)
            owner=ProcessJob();worker=None
            try:
                with (directory/'agent-library-worker.log').open('ab') as log:
                    worker=subprocess.Popen([str(python),'-u',str(root/'tools/agent-library-workflow.py'),'--run-id',run],cwd=root,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                        creationflags=subprocess.CREATE_NO_WINDOW|0x00000004 if os.name=='nt' else 0,start_new_session=os.name!='nt')
                owner.attach_and_resume(worker)
            except Exception:
                if worker:worker.kill();worker.wait()
                owner.close();raise ValueError('Could not start the owner publishing workflow.') from None
            self.worker=worker;self.owner=owner;self.last_run=run
            return {'started':True,'run_id':run}

    def schedule(self,enabled,minutes,approved=False):
        if type(enabled) is not bool or type(minutes) is not int or not 15<=minutes<=43200:raise ValueError('Choose a repeat interval of 15 minutes to 30 days.')
        if enabled and approved is not True:raise ValueError('Approve recurring owner publication first.')
        with self.lock:
            data=self._read()
            if not data:raise ValueError('This is not the registered owner publisher.')
            data['schedule']={'enabled':enabled,'minutes':minutes,'next_run':time.time()+minutes*60};self._save(data)
        return self.status()

    def open(self):
        if self.thread and self.thread.is_alive():return
        self.stop_event.clear()
        def loop():
            while not self.stop_event.wait(15):
                if not self.enabled():continue
                try:
                    state=self.status()
                    if state.get('result',{}).get('state') in ('failed','interrupted') and getattr(self,'last_run',''):
                        with self.lock:
                            data=self._read()
                            if data and data['schedule']['enabled']:data['schedule']['enabled']=False;self._save(data)
                        continue
                    with self.lock:
                        data=self._read()
                        if not data or not data['schedule']['enabled'] or data['schedule']['next_run']>time.time():continue
                        data['schedule']['next_run']=time.time()+data['schedule']['minutes']*60;self._save(data)
                    self.start(True)
                except Exception:
                    # Stop repeated failing unattended runs. The panel exposes
                    # registration/status failures without credentials or logs.
                    with self.lock:
                        try:
                            data=self._read()
                            if data:data['schedule']['enabled']=False;self._save(data)
                        except ValueError:pass
        self.thread=threading.Thread(target=loop,daemon=True,name='SakuraOwnerLibrary');self.thread.start()

    def close(self):
        self.stop_event.set()
        with self.lock:
            if self.owner:self.owner.close();self.owner=None

    def fingerprint(self):
        data=self._read()
        if not data:raise ValueError('This installation is not the registered owner publisher.')
        return hashlib.sha256(json.dumps({'account':data['account_hash'],'root':data['root'],'hashes':data['hashes']},sort_keys=True).encode()).hexdigest()


owner_library=OwnerLibrary()

