"""Resumable second-account publication with explicit verified progress."""
import importlib.util,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    os.environ['SAKURA_JIO_ACCOUNT']='account2'
    directory=ROOT.parent/'private-model-library-account2-pmx';status=directory/'publication-completion.json'
    def record(state,**extra):
        temp=status.with_suffix('.tmp');temp.write_text(json.dumps({'state':state,'updated_at':time.time(),**extra}),encoding='utf-8');temp.replace(status)
    record('syncing')
    try:
        result=subprocess.run([sys.executable,'-u',str(ROOT/'tools/sync-jio-library.py'),'--require-lock'],cwd=ROOT)
        if result.returncode:raise ValueError('Second-account sync stopped; completed files are retained for retry.')
        record('checking_authenticated_download')
        spec=importlib.util.spec_from_file_location('verify_jio',ROOT/'tools/verify-jio-publication.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        result=module.verify(ROOT);record('complete',**result);print(json.dumps(result),flush=True)
    except Exception as error:
        record('failed',error=str(error)[:250] if isinstance(error,ValueError) else type(error).__name__);return 2
    return 0
if __name__=='__main__':raise SystemExit(main())
