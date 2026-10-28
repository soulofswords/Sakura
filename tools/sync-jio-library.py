"""Owner command: publish model folders added to Jio's existing PMX game tree.

Run on this publisher PC; never bundled or enabled on tester machines.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import requests
from jio_library_owner import private_directory,account_id,JioConnection

ROOT=Path(__file__).resolve().parents[1]


def main():
    bundled=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
    if bundled.is_dir() and not os.environ.get('NODE_PATH'):os.environ['NODE_PATH']=str(bundled)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory-only',action='store_true')
    parser.add_argument('--additions-only',action='store_true',help='Publish additions without recreating existing packages. Full sync remains the default for source edits/deletions.')
    parser.add_argument('--all-accounts',action='store_true',help='Sync each configured storage account; one failed account does not skip another.')
    parser.add_argument('--asset-kind',choices=['character','stage','prop'],default='character')
    parser.add_argument('--require-lock',action='store_true',help='Fail rather than report success when another owner workflow holds the lock.')
    args=parser.parse_args()
    if args.all_accounts:
        failed=[]
        for account in ('primary','account2'):
            folder=ROOT.parent/('private-model-library'+('' if account=='primary' else '-account2'))
            if account!='primary' and not (folder/'server-enabled.json').is_file():continue
            flags=[flag for flag,enabled in (('--inventory-only',args.inventory_only),('--additions-only',args.additions_only),('--require-lock',args.require_lock)) if enabled]+['--asset-kind',args.asset_kind]
            result=subprocess.run([sys.executable,str(Path(__file__).resolve()),*flags],cwd=ROOT,env={**os.environ,'SAKURA_JIO_ACCOUNT':account})
            if result.returncode:failed.append(account)
        if failed:raise ValueError('Sync needs attention for: '+', '.join(failed)+'. Other configured accounts were still checked.')
        return
    if account_id()!='primary' and not (private_directory()/'server-enabled.json').is_file():raise ValueError('Second-account server routing must be deployed and verified before publication.')
    directory=private_directory('pmx' if args.asset_kind=='character' else args.asset_kind);directory.mkdir(exist_ok=True)
    if sys.platform=='win32':
        import msvcrt
        sync_lock=(directory/'jio-sync.lock').open('a+b');sync_lock.seek(0);sync_lock.write(b'1');sync_lock.flush();sync_lock.seek(0)
        try:msvcrt.locking(sync_lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            if args.require_lock:raise ValueError('Another owner library sync is already running.') from None
            print('A library sync is already running; this check was skipped.',flush=True);return
    def run(arguments,env=None):
        result=subprocess.run(arguments,cwd=ROOT,env=env)
        if result.returncode:raise ValueError('Owner library sync stopped. Review the preceding error; existing models were kept.')
    python=sys.executable
    command=[python,'tools/sync-jio-pmx-sources.py','--asset-kind',args.asset_kind]
    if not args.inventory_only:command.append('--prepare')
    if args.additions_only:command.append('--additions-only')
    run(command)
    if args.inventory_only:return
    if args.asset_kind!='character' and not (directory/'prepared-models.json').is_file():return
    environment=os.environ.copy();environment['SAKURA_LIBRARY_PREVIEW_PMX_ROOT']=str(directory/'jio-source')
    # Use a dedicated child process and close it after preview generation.
    try:
        if requests.get('http://127.0.0.1:8796/static/library-audit.html',timeout=2).status_code==200:
            raise ValueError('A library preview server is already running. Close that owner preview job before syncing a different source tree.')
    except requests.RequestException:pass
    server=subprocess.Popen([python,'tools/library-preview-server.py'],cwd=ROOT,env=environment,
                             creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        ready=False
        for _ in range(30):
            try:
                if requests.get('http://127.0.0.1:8796/static/library-audit.html',timeout=1).status_code==200:ready=True;break
            except requests.RequestException:pass
            time.sleep(.2)
        if not ready:raise ValueError('Owner preview server did not start.')
        # Render the complete pending set first. Uploading the full catalogue
        # after every six frames repeatedly scans large, already-verified trees
        # and stalls preview generation on a slow uplink.
        run(['node','tools/render-pmx-library-previews.cjs',str(directory)],env=environment)
    finally:
        server.terminate();server.wait(timeout=10)
    remote='PMX'
    if args.asset_kind!='character':
        import json
        inventory=json.loads((directory/'jio-source-inventory.json').read_text(encoding='utf-8'))
        remote=inventory.get('source_root','Stages' if args.asset_kind=='stage' else 'Tools & Props')
    run([python,'tools/upload-library-jio.py','--directory',str(directory),'--remote-folder',remote+'/Sakura library packages','--workers','3'])
    run([python,'tools/publish-library-jio.py','--directory',str(directory),'--configure'])
    if args.asset_kind!='character':return
    if account_id()!='primary' and JioConnection().store.load().get('folder_name')=='PMX':
        print('PMX-only storage account synced.',flush=True);return
    run([python,'tools/sync-jio-live2d-sources.py'])
    live2d=private_directory()
    run([python,'tools/upload-library-jio.py','--directory',str(live2d),'--workers','3'])
    run([python,'tools/publish-library-jio.py','--directory',str(live2d)])
    print('Jio PMX and Live2D libraries synced. Signed-in galleries refresh within one minute.',flush=True)


if __name__=='__main__':main()
