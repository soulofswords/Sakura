"""Finish an owner upload already in progress and verify hosted downloads.

Runs quietly without launching Sakura. Completion/failure is recorded for the
owner's follow-up automation; it never reports a pending transfer as complete.
"""
import argparse
import ctypes
from ctypes import wintypes
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT.parent/'private-model-library-pmx'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--wait-pid',type=int,action='append',default=[]);args=parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    import msvcrt
    lock=(DIRECTORY/'jio-sync.lock').open('a+b');lock.seek(0);lock.write(b'1');lock.flush();lock.seek(0)
    try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:raise ValueError('A full owner sync is already running.') from None
    status=DIRECTORY/'publication-completion.json'
    def record(state,**values):
        temporary=status.with_suffix('.tmp');temporary.write_text(json.dumps({'state':state,'updated_at':time.time(),**values},ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(status)
    record('waiting_for_current_upload')
    try:
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];kernel.WaitForSingleObject.restype=wintypes.DWORD
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        for pid in args.wait_pid:
            handle=kernel.OpenProcess(0x00100000,False,pid)
            if not handle:continue
            try:
                deadline=time.monotonic()+8*3600
                while kernel.WaitForSingleObject(handle,30000)==258:
                    if time.monotonic()>deadline:raise ValueError('The first upload did not finish within eight hours.')
            finally:kernel.CloseHandle(handle)
        log=DIRECTORY/'publication-finish.log'
        environment={**os.environ,'PYTHONIOENCODING':'utf-8'}
        def run(arguments):
            with log.open('a',encoding='utf-8') as output:
                return subprocess.run([sys.executable,*arguments],cwd=ROOT,env=environment,stdout=output,stderr=subprocess.STDOUT).returncode
        record('uploading_remaining_packages_and_previews')
        for attempt in range(3):
            if run(['tools/upload-library-jio.py','--directory',str(DIRECTORY),'--remote-folder','PMX/Sakura library packages','--workers','3'])==0:break
            if attempt==2:raise ValueError('Upload did not finish after resumed passes. Review the private owner log.')
            time.sleep(15)
        expected=json.loads((DIRECTORY/'prepared-models.json').read_text(encoding='utf-8'))
        uploaded=json.loads((DIRECTORY/'jio-uploaded-assets.json').read_text(encoding='utf-8'))['assets']
        if any(not v.get('preview') or not uploaded.get(k+'.webp',{}).get('verified') or not uploaded.get(k+'.zip',{}).get('verified') or uploaded[k+'.zip']['sha256']!=v['sha256'] for k,v in expected.items()):raise ValueError('A package or preview is not verified.')
        record('publishing')
        if run(['tools/publish-library-jio.py','--configure','--directory',str(DIRECTORY)]):raise ValueError('Publication did not finish. Verified uploads were retained.')
        record('checking_authenticated_download')
        installed=ROOT.parent/'Sakura Companion/Sakura';sys.path.insert(0,str(installed))
        import requests
        from agent_connections import secret_get,secret_set
        from model_library import ModelLibrary
        from model_library_config import SUPABASE_URL,SUPABASE_PUBLISHABLE_KEY
        from PIL import Image
        config=secret_get('model-library')
        if config.get('refresh_token'):
            response=requests.post(SUPABASE_URL+'/auth/v1/token?grant_type=refresh_token',headers={'apikey':SUPABASE_PUBLISHABLE_KEY},json={'refresh_token':config['refresh_token']},timeout=30)
            if response.status_code!=200:raise ValueError('Sign in to Sakura to finish the authenticated download check.')
            data=response.json();config.update(token=data['access_token'],refresh_token=data['refresh_token'],expires_at=time.time()+data.get('expires_in',3600));secret_set('model-library',config)
        with tempfile.TemporaryDirectory(prefix='library-install-check-',dir=DIRECTORY) as staging:
            library=ModelLibrary(staging,lambda:config);models=library.catalogue()['models'];found={m['id']:m for m in models}
            if any(k not in found or found[k]['sha256']!=v['sha256'] or not found[k]['preview'] for k,v in expected.items()):raise ValueError('The live catalogue does not match the verified packages.')
            sample=min((v for v in expected.values() if v['name'].startswith('Ananta /')),key=lambda v:v['bytes'])
            result=library.install(sample['id'])
            if len(result['models'])!=1:raise ValueError('Downloaded variant did not contain exactly one PMX.')
            preview=Image.open(io.BytesIO(library.preview(sample['id'])))
            if preview.n_frames<12:raise ValueError('Published preview does not rotate.')
        record('complete',pmx_looks=len(expected),verified_previews=len(expected),sample_download=sample['name'],sample_install_verified=True)
        print('Complete: all PMX looks and previews published; authenticated download verified.',flush=True)
    except Exception as error:
        record('failed',error=str(error) if isinstance(error,ValueError) else type(error).__name__)
        raise

if __name__=='__main__':main()
