"""Read-only installation diagnostics. Does not start models or contact cloud services."""
import concurrent.futures
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit


def local_health(endpoints,timeout=1):
    import requests
    def probe(item):
        name,url=item;parsed=urlsplit(url)
        if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost','::1') or parsed.username or parsed.password:
            return {'engine':name,'ready':False,'reason':'Only explicit loopback HTTP health probes are allowed.'}
        try:
            with requests.Session() as session:
                session.trust_env=False # A proxy must not turn a local health probe into an external request.
                response=session.get(url,timeout=(timeout,timeout),allow_redirects=False)
            return {'engine':name,'ready':response.status_code==200,'status':response.status_code}
        except requests.RequestException:return {'engine':name,'ready':False,'reason':'Not listening or timed out.'}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(probe,list(endpoints.items())[:8]))


def diagnose(root=None,probe=False):
    root=Path(root or Path(__file__).resolve().parent)
    required=('requests','fastapi','uvicorn','PIL','psutil','cryptography','mcp','playwright')
    modules={name:importlib.util.find_spec(name) is not None for name in required}
    files={name:(root/name).is_file() for name in ('static/index.html','static/assets/agent.html','static/js/model-viewer.js','static/js/pmx-reference-lighting.js','static/model-library-preview.html')}
    free=shutil.disk_usage(root).free
    result={'ok':all(modules.values()) and all(files.values()),'python':sys.version.split()[0],
            'platform':sys.platform,'modules':modules,'files':files,'disk_free_gib':round(free/1024**3,2),
            'warnings':[],'cloud_probed':False,'model_started':False}
    if free<2*1024**3:result['warnings'].append('Less than 2 GiB free. Model downloads need additional space.')
    if sys.platform=='win32' and importlib.util.find_spec('PySide6') is None:result['warnings'].append('PySide6 is missing; the desktop window cannot start.')
    if probe:result['local_engines']=local_health({'ollama':'http://127.0.0.1:11434/api/tags'})
    return result


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--json',action='store_true');parser.add_argument('--probe-local',action='store_true');args=parser.parse_args()
    result=diagnose(probe=args.probe_local)
    print(json.dumps(result,indent=2) if args.json else 'Sakura doctor: '+('PASS' if result['ok'] else 'Needs attention')+'\n'+json.dumps(result,indent=2))
    return 0 if result['ok'] else 1

if __name__=='__main__':raise SystemExit(main())
