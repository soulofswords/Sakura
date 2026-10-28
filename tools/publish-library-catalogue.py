"""Publish uploaded model records through a temporary, scoped owner endpoint."""
import argparse
import json
from pathlib import Path
import sys
import time
import requests

if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--app',required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--url',required=True)
    parser.add_argument('--once',action='store_true',help='Publish completed uploads once; do not wait for unfinished transfers.')
    args=parser.parse_args();sys.path.insert(0,args.app)
    if list(Path(args.app).glob('sakura_core*.pyd')):__import__('sakura_core')
    from agent_connections import secret_get
    token=secret_get('library-publisher-setup')['token']
    progress=args.output/'published-models.json'
    try:published=json.loads(progress.read_text(encoding='utf-8'))
    except (OSError,ValueError):published={}
    deadline=time.monotonic()+12*3600
    while time.monotonic()<deadline:
        try:uploaded=json.loads((args.output/'uploaded-models.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):uploaded={}
        for identifier,entry in uploaded.items():
            if published.get(identifier)==entry['sha256']:continue
            r=requests.post(args.url,headers={'Authorization':'Bearer '+token},json=entry,timeout=30)
            if r.status_code!=200:raise ValueError('Catalogue publication was refused for '+entry['name']+' (HTTP '+str(r.status_code)+').')
            published[identifier]=entry['sha256']
            draft=progress.with_suffix('.tmp');draft.write_text(json.dumps(published,indent=2),encoding='utf-8');draft.replace(progress)
            print('Published '+str(len(published))+': '+entry['name'],flush=True)
        if args.once:break
        catalogue=args.output/'catalogue.json'
        if catalogue.is_file():
            prepared=json.loads(catalogue.read_text(encoding='utf-8'))['models']
            if all(published.get(entry['id'])==entry['sha256'] for entry in prepared):break
        time.sleep(10)
    print('Published catalogue pass finished: '+str(len(published)),flush=True)


if __name__=='__main__':main()
