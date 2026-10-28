"""Run the fixed owner sync pipeline and report verified completion, no raw logs."""
import argparse
import os
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);args=parser.parse_args()
    import re
    if not re.fullmatch('[a-f0-9]{32}',args.run_id):raise ValueError('Invalid workflow ID.')
    folder=ROOT.parent/'private-model-library-pmx';status=folder/'agent-library-status.json'
    def record(state,message,**extra):
        temporary=status.with_suffix('.tmp');temporary.write_text(json.dumps({'run_id':args.run_id,'state':state,'message':message,'updated_at':time.time(),**extra}),encoding='utf-8');temporary.replace(status)
    record('starting','Starting owner library sync.')
    try:
        record('syncing','Checking Jio folders, validating models, generating previews and publishing verified packages.')
        failures=[]
        for account in ('primary','account2'):
            state=ROOT.parent/('private-model-library'+('' if account=='primary' else '-account2'))/'.jio-owner-session.bin'
            if account!='primary' and (not state.is_file() or not (state.parent/'server-enabled.json').is_file()):continue
            environment={**os.environ,'SAKURA_JIO_ACCOUNT':account}
            with (folder/'agent-library-pipeline.log').open('ab') as log:
                result=subprocess.run([sys.executable,str(ROOT/'tools/sync-jio-library.py'),'--require-lock','--additions-only'],cwd=ROOT,env=environment,stdout=log,stderr=log)
            if result.returncode:failures.append(account)
        if failures:raise ValueError('Library sync needs attention for '+', '.join(failures)+'. Other accounts were checked; verified transfers were kept for retry. See the private owner log.')
        record('verifying','Checking the authenticated catalogue and a real model install.')
        spec=importlib.util.spec_from_file_location('jio_publication_verify',ROOT/'tools/verify-jio-publication.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        checked=module.verify(ROOT)
        record('complete','Published library verified, including real downloads.',**checked)
    except Exception as error:
        record('failed',str(error)[:400] if isinstance(error,ValueError) else 'Owner sync failed. Check the private log; no raw provider error is exposed.')
        return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
