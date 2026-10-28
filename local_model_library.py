"""Read-only local character previews; paths stay inside the user's model library."""
import hashlib
from pathlib import Path
import threading
from model_library_previews import live2d_preview

_preview_lock=threading.Lock()


def router(root,local_check):
    from fastapi import APIRouter,Request
    from fastapi.responses import FileResponse,JSONResponse
    from starlette.concurrency import run_in_threadpool
    root=Path(root).resolve()
    routes=APIRouter(prefix='/api/local-model-library')

    def folder_names():
        import json
        names={}
        for record in (root/'.library').glob('*.json'):
            try:
                if record.stat().st_size>1_000_000:continue
                data=json.loads(record.read_text(encoding='utf-8'))
                label=str(data.get('name','')).replace('\\','/').split('/')[-1].strip()[:180]
                if not label:continue
                for model in data.get('models',[]):
                    parts=Path(model).parts
                    if len(parts)>=3 and parts[0] in ('pmx','vrm','live2d') and parts[1].startswith('import-') and (root/model).resolve().is_relative_to(root) and (root/model).is_file():
                        names[parts[0]+'/'+parts[1]]=label
            except (OSError,ValueError,TypeError,AttributeError):continue
        from collections import Counter
        counts=Counter((key.split('/')[0],label.casefold()) for key,label in names.items())
        for key,label in list(names.items()):
            kind,folder=key.split('/',1)
            if counts[kind,label.casefold()]>1 or (root/kind/label).exists():names[key]=label+' '+folder.removeprefix('import-')
        return names

    @routes.get('/folder-names')
    async def names(request:Request):
        if not local_check(request):return JSONResponse({'error':'Use Sakura on this computer.'},403)
        return {'names':await run_in_threadpool(folder_names)}

    def image(model):
        descriptor=(root/model).resolve()
        if (not descriptor.is_relative_to(root/'live2d') or not descriptor.is_file()
                or not descriptor.name.endswith('.model3.json')):
            raise ValueError('Choose a local Live2D character.')
        key=hashlib.sha256((str(descriptor)+str(descriptor.stat().st_mtime_ns)+str(descriptor.parent.stat().st_mtime_ns)).encode()).hexdigest()
        cache=root/'.sakura'/'library-previews';cache.mkdir(parents=True,exist_ok=True)
        target=cache/(key+'.webp')
        with _preview_lock:
            if not target.is_file() and not live2d_preview(descriptor.parent,target):
                raise ValueError('No character preview image.')
        return target

    @routes.get('/preview')
    async def preview(request:Request,model:str):
        if not local_check(request):return JSONResponse({'error':'Use Sakura on this computer.'},403)
        try:target=await run_in_threadpool(image,model)
        except (ValueError,OSError):return JSONResponse({'error':'No preview image.'},404)
        return FileResponse(target,media_type='image/webp',headers={'X-Content-Type-Options':'nosniff','Cache-Control':'private, max-age=300'})
    return routes
