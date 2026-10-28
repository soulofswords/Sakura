"""Owner-only publication of verified Jio library packages to hosted Sakura."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
import threading
import time
import requests
from jio_library_owner import account_id, EncryptedState,JioConnection

URL='https://gclwwyznseuuixnbwpyz.supabase.co/functions/v1/sakura-library-jio-owner'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=Path(__file__).resolve().parents[2]/'private-model-library')
    parser.add_argument('--configure',action='store_true')
    args=parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
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
                stamp=entry['sha256']+('|preview='+str(model['jio_preview_object_key']) if entry['format']=='pmx' else '')
                return key,stamp
            except (ValueError,requests.RequestException):
                if attempt==3:raise
                time.sleep(2**attempt)
    failures=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(one,pair):pair[0] for pair in prepared.items()
              if published.get(pair[0])!=(pair[1]['sha256']+('|preview='+str(uploaded['assets'].get(pair[0]+'.webp',{}).get('objectKey') if pair[1].get('preview') else None) if pair[1]['format']=='pmx' else ''))
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
