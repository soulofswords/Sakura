"""Dedicated scenery roots; owner cloud folders use the same public namespaces."""
from pathlib import Path

FOLDERS={'stage':'Stages','prop':'Tools & Props'}


def asset_kind(name):
    first=str(name).replace('\\','/').split('/')[0].strip().casefold()
    if first in ('stage','stages'):return 'stage'
    if first in ('tools & props','tools and props'):return 'prop'
    return 'character'


def local_assets(root,kind):
    if kind not in FOLDERS:raise ValueError('Choose Stages or Tools & Props.')
    root=Path(root);folder=root/'pmx'/FOLDERS[kind];rows=[]
    if not folder.exists():return rows
    for path in sorted(folder.rglob('*')):
        if path.suffix.lower()!='.pmx' or not path.is_file() or not path.resolve().is_relative_to(folder.resolve()):continue
        relative=path.relative_to(folder)
        try:
            with path.open('rb') as source:valid=source.read(4)==b'PMX '
        except OSError:valid=False
        if valid:rows.append({'path':path.relative_to(root).as_posix(),'name':path.stem,'folders':list(relative.parts[:-1]),'asset_kind':kind})
    return rows


def router(root,local_check):
    from fastapi import APIRouter,File,Form,Request,UploadFile
    from fastapi.responses import JSONResponse
    from starlette.concurrency import run_in_threadpool
    from model_import import import_package,MAX_BYTES
    routes=APIRouter(prefix='/api/scenery')
    @routes.get('/assets')
    async def listing(request:Request,kind:str='stage'):
        if not local_check(request):return JSONResponse({'error':'Local access required.'},403)
        try:return {'models':await run_in_threadpool(local_assets,root,kind)}
        except ValueError as error:return JSONResponse({'error':str(error)},400)
    @routes.post('/import')
    async def importing(request:Request,files:list[UploadFile]=File(...),kind:str=Form('stage')):
        if not local_check(request):return JSONResponse({'error':'Local access required.'},403)
        try:
            if kind not in FOLDERS:raise ValueError('Choose Stages or Tools & Props.')
            if not 0<len(files)<=5000:raise ValueError('Choose up to 5,000 files.')
            total=0;contents=[]
            for upload in files:
                content=await upload.read(MAX_BYTES-total+1);total+=len(content)
                if total>MAX_BYTES:raise ValueError('Asset packages must be under 512 MB.')
                contents.append((upload.filename or '',content))
            result=await run_in_threadpool(import_package,root,contents,'pmx','', '',kind)
            return {'ok':True,**result}
        except ValueError as error:return JSONResponse({'error':str(error)},400)
    return routes
