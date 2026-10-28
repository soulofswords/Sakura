"""Owner-only publication of verified Jio library packages to hosted Sakura."""
import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
import threading
import time
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model_library_paths import pmx_library_name
from jio_library_owner import account_id, EncryptedState,JioConnection

URL='https://gclwwyznseuuixnbwpyz.supabase.co/functions/v1/sakura-library-jio-owner'


def publication_stamp(entry, portrait):
    """Metadata-only folder repairs must publish even when ZIP bytes are unchanged."""
    metadata={key:entry.get(key) for key in ('name','format','mobile_compatible','preview')}
    return entry['sha256']+'|metadata='+hashlib.sha256(json.dumps(metadata,sort_keys=True).encode()).hexdigest()+'|preview='+str(portrait if entry.get('preview') else None)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=Path(__file__).resolve().parents[2]/'private-model-library')
    parser.add_argument('--configure',action='store_true')
    args=parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    if sys.platform=='win32':
        import msvcrt
        publication_lock=(args.directory/'jio-publication.lock').open('a+b')
        publication_lock.seek(0);publication_lock.write(b'1');publication_lock.flush();publication_lock.seek(0)
        try:msvcrt.locking(publication_lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            print('An owner publication pass is already running; duplicate pass skipped.',flush=True)
            return 0
    if args.configure:
        owner=JioConnection();owner.resume()
    saved=EncryptedState().load()
    proof=EncryptedState(Path(__file__).resolve().parents[2]/'private-model-library'/'.jio-publish-proof.bin').load()['token']
    headers={'X-Sakura-Owner':proof}
    if args.configure:
        # Send only necessary session fields, never the whole local account store.
        response=requests.post(URL,headers=headers,json={'operation':'configure','account':account_id(),'storage':{
            'provider':'jio','session':saved['session']}},timeout=40,allow_redirects=False)
        if response.status_code!=200:raise ValueError('Private Jio server configuration failed (HTTP '+str(response.status_code)+').')
        print('Private Jio connection configured on the authenticated library server.',flush=True)
    prepared=json.loads((args.directory/'prepared-models.json').read_text(encoding='utf-8'))
    for entry in prepared.values():
        source=entry.get('variant_model') or str(entry.get('preview_model','')).removeprefix('pmx/')
        if entry.get('format')=='pmx' and source:entry['name']=pmx_library_name(source)
    uploaded=json.loads((args.directory/'jio-uploaded-assets.json').read_text(encoding='utf-8'))
    if uploaded['userId']!=saved['session']['userId']:raise ValueError('Upload ledger account mismatch.')
    ledger=args.directory/'jio-published-models.json'
    try:published=json.loads(ledger.read_text())
    except FileNotFoundError:published={}
    def one(pair):
        key,entry=pair
        package=uploaded['assets'].get(key+'.zip',{})
        portrait=uploaded['assets'].get(key+'.webp',{})
        if not package.get('verified') or package.get('sha256')!=entry['sha256'] or (entry.get('preview') and not portrait.get('verified')):
            raise ValueError('Only checksum-verified assets can be published.')
        model={**entry,'jio_object_key':package['objectKey'],
               'jio_preview_object_key':portrait.get('objectKey') if entry.get('preview') else None}
        for attempt in range(4):
            try:
                response=requests.post(URL,headers=headers,json={'operation':'publish','account':account_id(),'folderKey':uploaded['folderKey'],'model':model},timeout=50,allow_redirects=False)
                if response.status_code!=200:
                    # Endpoint messages are fixed and never contain account credentials.
                    message=response.json().get('error','Publication refused.')
                    raise ValueError(str(message)[:150])
                stamp=publication_stamp(entry,model['jio_preview_object_key'])
                return key,stamp
            except (ValueError,requests.RequestException):
                if attempt==3:raise
                time.sleep(2**attempt)
    failures=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(one,pair):pair[0] for pair in prepared.items()
              if published.get(pair[0])!=publication_stamp(pair[1],uploaded['assets'].get(pair[0]+'.webp',{}).get('objectKey'))
              and uploaded['assets'].get(pair[0]+'.zip',{}).get('verified')
              and (not pair[1].get('preview') or uploaded['assets'].get(pair[0]+'.webp',{}).get('verified'))}
        for future in as_completed(jobs):
            try:
                key,sha=future.result();published[key]=sha
                temporary=ledger.with_suffix('.tmp');temporary.write_text(json.dumps(published,indent=2));temporary.replace(ledger)
                print(f'Published {sum(key in published for key in prepared)}/{len(prepared)}',flush=True)
            except Exception as exc:
                failures.append(jobs[future]);print('Publication deferred: '+jobs[future]+' ('+type(exc).__name__+')',flush=True)
    print(json.dumps({'published':sum(key in published for key in prepared),'failed':failures}),flush=True)
    return 2 if failures else 0


if __name__=='__main__':raise SystemExit(main())
