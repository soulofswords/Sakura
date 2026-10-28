"""Upload prepared packages into a private, app-created Drive folder. No sharing changes."""
import argparse
import json
from pathlib import Path
import sys
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests

if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--app',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--configure-url');parser.add_argument('--wait',action='store_true');args=parser.parse_args()
    if sys.platform=='win32':
        import msvcrt
        task_lock=(args.output/'upload.lock').open('a+b');task_lock.seek(0);task_lock.write(b'1');task_lock.flush();task_lock.seek(0)
        try:msvcrt.locking(task_lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            print('Another upload pass is running.');return
    sys.path.insert(0,args.app)
    if list(Path(args.app).glob('sakura_core*.pyd')):__import__('sakura_core')
    from agent_connections import secret_get,secret_set
    secret=secret_get('library-storage-google')
    if secret.get('scope')!='https://www.googleapis.com/auth/drive.file':raise ValueError('Authorize isolated publisher storage first.')
    token_at=0;headers={}
    def auth():
        nonlocal token_at,headers
        if time.monotonic()-token_at>2400 or not headers:
            r=requests.post('https://oauth2.googleapis.com/token',data={k:secret[k] for k in ('client_id','client_secret','refresh_token')}|{'grant_type':'refresh_token'},timeout=30)
            if r.status_code!=200:raise ValueError('Publisher storage authorization expired.')
            headers={'Authorization':'Bearer '+r.json()['access_token']};token_at=time.monotonic()
        return headers
    if not secret.get('folder_id'):
        r=requests.post('https://www.googleapis.com/drive/v3/files',headers=auth(),json={
            'name':'Sakura Cloud Model Library','mimeType':'application/vnd.google-apps.folder',
            'description':'Private runtime packages published through signed-in Sakura access.'},timeout=30)
        if r.status_code!=200:raise ValueError('Could not create the private publisher folder.')
        secret['folder_id']=r.json()['id'];secret_set('library-storage-google',secret)
        print('Created private Sakura publisher folder. Original model folders were not changed.',flush=True)
    if args.configure_url:
        setup=secret_get('library-publisher-setup')
        response=requests.post(args.configure_url,headers={'Authorization':'Bearer '+setup['token']},json={k:secret[k] for k in ('client_id','client_secret','refresh_token','scope')},timeout=30)
        if response.status_code!=200:raise ValueError('Protected storage configuration was refused.')
        print('Dedicated storage credential encrypted in Supabase Vault.',flush=True)
    progress=args.output/'uploaded-models.json'
    try:uploaded=json.loads(progress.read_text(encoding='utf-8'))
    except (OSError,ValueError):uploaded={}
    remote={}
    listing=requests.get('https://www.googleapis.com/drive/v3/files',headers=auth(),params={
        'q':"'"+secret['folder_id']+"' in parents and trashed=false",'pageSize':1000,
        'fields':'files(id,name,size,md5Checksum)'},timeout=30)
    if listing.status_code==200:
        remote={entry['name']:entry for entry in listing.json().get('files',[])}
    def upload(path):
        existing=remote.get(path.name)
        if existing and int(existing.get('size',0))==path.stat().st_size:
            with path.open('rb') as source:digest=hashlib.file_digest(source,'md5').hexdigest()
            if digest==existing.get('md5Checksum'):return existing['id']
        headers={**auth(),'X-Upload-Content-Type':'application/octet-stream','X-Upload-Content-Length':str(path.stat().st_size)}
        r=requests.post('https://www.googleapis.com/upload/drive/v3/files',params={'uploadType':'resumable','fields':'id'},headers=headers,
            json={'name':path.name,'parents':[secret['folder_id']]},timeout=30,allow_redirects=False)
        if r.status_code!=200:raise ValueError('Could not start a model upload.')
        location=r.headers.get('Location','')
        if not location.startswith('https://www.googleapis.com/'):raise ValueError('Unexpected upload host.')
        with path.open('rb') as stream:r=requests.put(location,headers={**auth(),'Content-Length':str(path.stat().st_size)},data=stream,timeout=(8,600),allow_redirects=False)
        if r.status_code not in (200,201):
            try:reason=r.json().get('error',{}).get('errors',[{}])[0].get('reason','unknown')
            except (ValueError,IndexError,AttributeError):reason='unknown'
            raise ValueError('A model upload did not finish (HTTP '+str(r.status_code)+', '+reason+').')
        identifier=r.json()['id']
        with path.open('rb') as source:digest=hashlib.file_digest(source,'md5').hexdigest()
        remote[path.name]={'id':identifier,'size':str(path.stat().st_size),'md5Checksum':digest}
        return identifier
    def upload_entry(identifier,entry):
        print('Uploading '+entry['name'],flush=True)
        for attempt in range(4):
            try:
                drive_id=upload(args.output/(identifier+'.zip'))
                preview_id=upload(args.output/(identifier+'.webp')) if entry.get('preview') else None
                return identifier,{**entry,'drive_file_id':drive_id,'preview_drive_file_id':preview_id,'published':True}
            except (requests.RequestException,ValueError) as error:
                if attempt==3:raise
                print('Retrying upload: '+str(error),flush=True);time.sleep(2**attempt)
    deadline=time.monotonic()+12*3600
    deferred=[]
    while True:
        try:prepared=json.loads((args.output/'prepared-models.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):prepared={}
        with ThreadPoolExecutor(max_workers=3) as workers:
            jobs=[workers.submit(upload_entry,identifier,entry) for identifier,entry in prepared.items() if identifier not in uploaded]
            for job in as_completed(jobs):
                try:identifier,entry=job.result()
                except (ValueError,requests.RequestException) as error:
                    deferred.append(str(error));print('Deferred upload: '+str(error),flush=True);continue
                uploaded[identifier]=entry
                draft=progress.with_suffix('.tmp');draft.write_text(json.dumps(uploaded,ensure_ascii=False,indent=2),encoding='utf-8');draft.replace(progress)
                print('Uploaded packages: '+str(len(uploaded)),flush=True)
        if deferred or not args.wait or time.monotonic()>deadline:break
        # catalogue.json is written only when the preparation pass finishes.
        if (args.output/'catalogue.json').is_file():
            final=json.loads((args.output/'catalogue.json').read_text(encoding='utf-8'))['models']
            if all(entry['id'] in uploaded for entry in final):break
        time.sleep(10)
    print('Upload pass complete: '+str(len(uploaded)),flush=True)
    return 2 if deferred else 0


if __name__=='__main__':raise SystemExit(main())
