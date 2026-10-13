"""Background PMX/VRM rendering audit with separate Markdown error reports."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
import uuid

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from owned_process import ProcessJob
for stream in (sys.stdout,sys.stderr):
    if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')

def owned(args,**kwargs):
    job=ProcessJob();process=None
    try:
        process=subprocess.Popen([str(arg) for arg in args],cwd=BASE,
            creationflags=(subprocess.CREATE_NO_WINDOW|0x00000004) if os.name=='nt' else 0,
            start_new_session=os.name!='nt',**kwargs)
        job.attach_and_resume(process);return job,process
    except BaseException:
        if process:process.kill();process.wait()
        job.close();raise

def markdown(state,fatal=None):
    models=state.get('models',[]);failures=[m for m in models if not m.get('ok')]
    warnings=[m for m in models if m.get('missingTextures')];live=state.get('live2d',[])
    text=['# Sakura model rendering check','',
          f"Checked: {len(models)} / {state.get('total','unknown')} selected 3D models. Full library: {state.get('libraryTotal','unknown')}.",
          f"Rendered successfully: {len(models)-len(failures)}. Failed: {len(failures)}. Models with missing-texture fallbacks: {len(warnings)}.",
          '','Complete: '+str(bool(state.get('complete'))),
          '','Models are rendered in a private headless browser. No companion window, microphone, AI model, shared Chrome profile, or saved screenshots are used.',
          '','Checks cover load/render errors, portrait and full-body visibility, invalid PMX geometry, non-finite bone transforms, WebGL errors/context loss, and missing-texture fallback responses.',
          '','A successful pixel check does not guarantee exact colours, perfect clothing/hair transparency, or absence of every clipping/mesh defect. Those still need visual review.']
    if fatal:text+=['','## Check failed','',str(fatal)]
    if failures:
        text+=['','## Rendering failures','']
        for model in failures:text+=['- `'+model['path'].replace('`','')+'`: '+str(model.get('error') or model.get('errors') or 'Renderer check failed')]
    if warnings:
        text+=['','## Missing textures / fallback assets','']
        for model in warnings:
            text+=['- `'+model['path'].replace('`','')+'`: '+str(len(model['missingTextures']))+' missing or failed asset requests. See results.json for URLs.']
    if live:
        text+=['','## Live2D','',f'{len(live)} Live2D entries were found. The app now has a Live2D runtime. This 3D-library audit does not render Live2D packages; use the Live2D background check to verify model files and expressions.']
    text+=['','## Per-model results','','| Model | Result | Vertices | Bones | Load/check seconds |','|---|---|---:|---:|---:|']
    for model in models:
        name=model['path'].replace('|','\\|').replace('`','')
        status='FAIL' if not model.get('ok') else 'WARN: texture fallback' if model.get('missingTextures') else 'PASS'
        text.append(f"| {name} | {status} | {model.get('vertices','')} | {model.get('bones','')} | {model.get('seconds','')} |")
    return '\n'.join(text)+'\n',bool(failures or warnings or live or fatal)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('C:/AI'))
    parser.add_argument('--filter',default='')
    parser.add_argument('--limit',type=int,default=0)
    parser.add_argument('--sample',action='store_true',help='First and last PMX plus first VRM; otherwise checks all models.')
    args=parser.parse_args(argv)
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    run=output/'model-render-reports'/('Render-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]);run.mkdir(parents=True)
    result=run/'results.json';state={};fatal=None;jobs=[];logs=[]
    try:
        if args.limit<0:raise ValueError('Limit must be zero (all models) or positive.')
        node=shutil.which('node')
        if not node:raise RuntimeError('Node.js is required for the rendering check.')
        environment=dict(os.environ,PYTHONUTF8='1',PYTHONUNBUFFERED='1')
        paths=[environment.get('NODE_PATH',''),str(BASE/'tools/model-check-deps/node_modules'),
            str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules')]
        environment['NODE_PATH']=os.pathsep.join(path for path in paths if path)
        dependency=subprocess.run([node,'-e',"require('playwright');console.log('Playwright ready')"],env=environment,capture_output=True,text=True,timeout=30)
        if dependency.returncode:raise RuntimeError('Playwright is missing. Run npm install --prefix "'+str(BASE/'tools/model-check-deps')+'" playwright, then try again.')
        candidates=[environment.get('SAKURA_AUDIT_BROWSER',''),
            str(Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Google/Chrome/Application/chrome.exe'),
            str(Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe')]
        browser=next((candidate for candidate in candidates if candidate and Path(candidate).is_file()),None)
        if not browser:raise RuntimeError('Install Chrome/Edge, or set SAKURA_AUDIT_BROWSER to a Chromium executable.')
        with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        url='http://127.0.0.1:'+str(port)
        log=(run/'server.log').open('wb');logs.append(log)
        job,server=owned([sys.executable,BASE/'tools/model-check-server.py','--port',str(port)],env=environment,stdout=log,stderr=subprocess.STDOUT);jobs.append((job,server))
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            if server.poll() is not None:raise RuntimeError('Private asset server failed to start. See server.log.')
            try:
                with urllib.request.urlopen(url+'/health',timeout=1) as response:
                    if json.load(response).get('service')=='sakura-private-render-check':break
            except OSError:time.sleep(.2)
        else:raise RuntimeError('Private asset server startup timed out.')
        environment.update(SAKURA_AUDIT_URL=url,SAKURA_AUDIT_RESULT=str(result),SAKURA_AUDIT_BROWSER=browser,
            SAKURA_AUDIT_FILTER=args.filter,SAKURA_AUDIT_LIMIT=str(args.limit),SAKURA_AUDIT_SAMPLE='1' if args.sample else '0')
        print('Checking models privately. Reports: '+str(run),flush=True)
        job,worker=owned([node,BASE/'tools/model-render-check.cjs'],env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace');jobs.append((job,worker))
        with (run/'worker.log').open('w',encoding='utf-8') as log:
            for line in worker.stdout:print(line.rstrip(),flush=True);log.write(line);log.flush()
        code=worker.wait()
        if result.exists():state=json.loads(result.read_text(encoding='utf-8'))
        if code not in (0,2) or not state.get('complete'):raise RuntimeError(state.get('fatal') or 'Rendering check did not finish. See worker.log.')
    except (Exception,KeyboardInterrupt) as error:
        fatal='Cancelled by user.' if isinstance(error,KeyboardInterrupt) else str(error)
        (run/'exception.md').write_text('# Model check error\n\n```text\n'+traceback.format_exc()+'\n```\n',encoding='utf-8')
        if result.exists():
            try:state=json.loads(result.read_text(encoding='utf-8'))
            except (ValueError,OSError):pass
    finally:
        for job,process in reversed(jobs):
            job.close()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        for log in logs:log.close()
    report,issues=markdown(state,fatal)
    (run/'Report.md').write_text(report,encoding='utf-8')
    (output/'Model-Rendering-Report.md').write_text(report+'\nFull results: '+str(run)+'\n',encoding='utf-8')
    errors=report if issues else '# Model rendering errors\n\nNo issues detected in the selected PMX/VRM checks.\n'
    (run/'Errors.md').write_text(errors,encoding='utf-8')
    (output/'Model-Rendering-Errors.md').write_text(errors+'\nFull results: '+str(run)+'\n',encoding='utf-8')
    print(('CHECK FAILED' if fatal else 'ISSUES DETECTED' if issues else 'CHECK PASSED')+': '+str(output/'Model-Rendering-Report.md'))
    return 1 if fatal else 2 if issues else 0

if __name__=='__main__':sys.exit(main())
