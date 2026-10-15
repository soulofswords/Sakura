"""Bounded, model-only transfer packages for an authenticated paired phone."""
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote,urlsplit
import uuid
import zipfile

ALLOWED={'.png','.jpg','.jpeg','.webp','.bmp','.tga','.dds','.spa','.sph','.json','.moc3','.mtn','.exp3','.txt'}

def bundle_model(url,root,cache):
    root=Path(root).resolve();parsed=urlsplit(str(url))
    if parsed.scheme or not parsed.path.startswith('/models/'):raise ValueError('Choose an imported model first.')
    relative=Path(unquote(parsed.path[len('/models/'):]).replace('\\','/'))
    source=(root/relative).resolve()
    if not source.is_relative_to(root) or not source.is_file():raise ValueError('Model is outside the model library.')
    kind='vrm' if source.suffix.lower()=='.vrm' else 'pmx' if source.suffix.lower()=='.pmx' else 'live2d' if source.name.lower().endswith('.model3.json') else None
    if not kind:raise ValueError('Choose a PMX, VRM or Live2D model.')
    files=[source] if kind=='vrm' else [p for p in source.parent.rglob('*') if p.is_file() and (p==source or p.suffix.lower() in ALLOWED)]
    return _bundle(source,source.parent,kind,files,cache)


def bundle_selected_folder(source,selected,kind,cache):
    """Only called after the PC user explicitly chooses a folder/file in the native picker."""
    selected=Path(selected).resolve();source=Path(source).resolve()
    root=selected.parent if kind=='vrm' else selected
    if kind not in ('pmx','vrm','live2d') or not source.is_file() or not source.is_relative_to(root):raise ValueError('Invalid selected model.')
    if kind=='vrm' and (source!=selected or source.suffix.lower()!='.vrm'):raise ValueError('Choose a single VRM file.')
    if kind=='pmx' and source.suffix.lower()!='.pmx':raise ValueError('Choose a PMX entry point.')
    if kind=='live2d' and not source.name.lower().endswith('.model3.json'):raise ValueError('Choose a Live2D entry point.')
    files=[source] if kind=='vrm' else [p for p in root.rglob('*') if p.is_file()]
    if (root/'sakura-mobile-model.json').exists():raise ValueError('The selected folder contains reserved mobile transfer metadata.')
    return _bundle(source,root,kind,files,cache)


def _bundle(source,root,kind,files,cache):
    if len(files)>2500 or sum(p.stat().st_size for p in files)>1_000_000_000:raise ValueError('Model exceeds the mobile transfer limit (1 GB / 2500 files).')
    for file in files:
        if file.is_symlink() or not file.resolve().is_relative_to(root):raise ValueError('Linked model files cannot be transferred.')
    entry=source.relative_to(root).as_posix()
    identifier=uuid.uuid4().hex
    folder=Path(cache);folder.mkdir(parents=True,exist_ok=True)
    target=folder/(identifier+'.zip')
    try:
        with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
            for file in files:archive.write(file,file.relative_to(root).as_posix())
            archive.writestr('sakura-mobile-model.json',json.dumps({'entry':entry,'format':kind,'name':source.stem}))
        if target.stat().st_size>500_000_000:raise ValueError('Compressed transfer exceeds 500 MB.')
        with target.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        return {'id':identifier,'name':source.stem,'format':kind,'entry':entry,'bytes':target.stat().st_size,'sha256':digest},target
    except Exception:
        target.unlink(missing_ok=True);raise
