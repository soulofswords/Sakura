"""Package only PMX categories the owner uploaded, retaining original textures.

Reads the Sakura model folder; does not edit models or the owner's raw Jio tree.
Runtime packages are prepared separately for authenticated cloud installation.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model_import import import_package, MAX_BYTES
from model_rig_validation import pmx_bone_names,validate_humanoid_names

CATEGORIES=('genshin impact','honkai impact 3rd','Honkai star rail','snowbreak','zenless zone zero')
ASSETS={'.pmx','.png','.jpg','.jpeg','.bmp','.tga','.dds','.sph','.spa','.gif','.webp','.txt','.md','.pdf','.json'}


def groups(root):
    for directory in sorted(root.iterdir()):
        if not directory.is_dir() or directory.name.casefold()=='sakura library packages':continue
        category=directory.name
        if any(directory.glob('*.pmx')):
            yield category,directory
            continue
        for character in sorted(directory.iterdir()):
            if not character.is_dir():continue
            total=sum(x.stat().st_size for x in character.rglob('*') if x.is_file() and x.suffix.lower() in ASSETS)
            # The Honkai MMD container groups many independent character folders.
            if total>MAX_BYTES or (category=='honkai impact 3rd' and character.name=='Honkai MMD'):
                parents=sorted({x.parent for x in character.rglob('*.pmx')})
                for parent in parents:
                    yield category,parent
            else:yield category,character


def variants(root):
    """One selectable humanoid per authored PMX; skip standalone props."""
    for category,folder in groups(root):
        good=[]
        for model in sorted(folder.rglob('*.pmx')):
            try:validate_humanoid_names(pmx_bone_names(model.read_bytes()),model.name);good.append(model)
            except ValueError:continue
        if len(good)<=1:
            yield category,folder,None
        else:
            for model in good:yield category,folder,model


def prepare(root,category,folder,output,previous,selected_model=None):
    relative=folder.relative_to(root).as_posix()
    identity=selected_model.relative_to(root).as_posix() if selected_model else relative
    identifier=('' if __import__('os').environ.get('SAKURA_JIO_ACCOUNT','primary')=='primary' else 'account2-')+'pmx-'+hashlib.sha256(identity.encode()).hexdigest()[:24]
    files=sorted(x for x in folder.rglob('*') if x.is_file() and x.suffix.lower() in ASSETS)
    if not files:raise ValueError('No runtime files.')
    if any(x.is_symlink() or not x.resolve().is_relative_to(root.resolve()) for x in files):raise ValueError('Linked assets are not allowed.')
    good,bad=[],[]
    for model in [x for x in files if x.suffix.lower()=='.pmx']:
        try:validate_humanoid_names(pmx_bone_names(model.read_bytes()),model.name);good.append(model)
        except ValueError:bad.append(model)
    if not good:raise ValueError('No importable humanoid PMX model in this folder.')
    if selected_model:
        if selected_model not in good:raise ValueError('Selected variant is not an importable humanoid.')
        good=[selected_model]
        # Preserve the original relative asset tree, but only import the chosen
        # PMX. Other outfits no longer appear as an accidental side effect.
        files=[x for x in files if x.suffix.lower()!='.pmx' or x==selected_model]
    files=[x for x in files if x not in bad]
    if len(files)>5000 or sum(x.stat().st_size for x in files)>MAX_BYTES:raise ValueError('Package exceeds importer limits.')
    fingerprint=hashlib.sha256('\n'.join(str(x.relative_to(folder))+':'+str(x.stat().st_size)+':'+str(x.stat().st_mtime_ns) for x in files).encode()).hexdigest()
    old=previous.get(identifier)
    if old and old.get('source_fingerprint')==fingerprint and (output/(identifier+'.zip')).is_file():return identifier,old
    target=output/(identifier+'.zip');temporary=target.with_suffix('.tmp')
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as archive:
        for file in files:archive.write(file,file.relative_to(folder).as_posix())
    if temporary.stat().st_size>MAX_BYTES:raise ValueError('Compressed package exceeds importer limits.')
    # Validate exactly the package users receive. Restores .tga names naturally
    # because packaging reads unchanged local originals, not inferred Jio names.
    with tempfile.TemporaryDirectory(prefix='sakura-pmx-publish-') as stage:
        import_package(stage,[(target.name,temporary.read_bytes())],'pmx')
    temporary.replace(target)
    with target.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
    primary=min(good,key=lambda x:(len(x.relative_to(folder).parts),len(x.name),x.name))
    title=folder.name if folder.name!='Honkai MMD' else primary.stem
    if selected_model:
        parts=[folder.name,*selected_model.parent.relative_to(folder).parts]
        # Keep wrapper paths so nested outfit folders remain navigable.
        if len(list(selected_model.parent.glob('*.pmx')))>1:
            parts.append(selected_model.stem)
        title=' / '.join(parts)
    return identifier,{'id':identifier,'name':category+' / '+title,'format':'pmx','bytes':target.stat().st_size,
        'sha256':sha,'version':sha[:12],'preview':False,'mobile_compatible':False,
        'source_folder':relative,'preview_model':'pmx/'+primary.relative_to(root).as_posix(),
        'source_fingerprint':fingerprint,'models':len(good),'excluded_non_avatar_models':len(bad),
        'variant_model':selected_model.relative_to(root).as_posix() if selected_model else None}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]/'models/pmx')
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[2]/'private-model-library-pmx')
    args=parser.parse_args();sys.stdout.reconfigure(encoding='utf-8');args.output.mkdir(exist_ok=True,parents=True)
    checkpoint=args.output/'prepared-models.json'
    try:prepared=json.loads(checkpoint.read_text(encoding='utf-8'))
    except FileNotFoundError:prepared={}
    previous=prepared;prepared={}
    failures=[];todo=list(variants(args.root));print('Character variants: '+str(len(todo)),flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(prepare,args.root,category,folder,args.output,previous,model):(category,folder) for category,folder,model in todo}
        for future in as_completed(jobs):
            category,folder=jobs[future]
            try:
                key,entry=future.result();prepared[key]=entry
                temporary=checkpoint.with_suffix('.tmp');temporary.write_text(json.dumps(prepared,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(checkpoint)
                print('Prepared '+str(len(prepared))+'/'+str(len(todo)),flush=True)
            except Exception as exc:
                failures.append({'folder':folder.relative_to(args.root).as_posix(),'error':str(exc)[:300]})
                print('Deferred '+folder.relative_to(args.root).as_posix(),flush=True)
    public=[{k:v for k,v in entry.items() if k not in ('source_folder','preview_model','source_fingerprint','models','excluded_non_avatar_models','variant_model')} for entry in prepared.values()]
    (args.output/'catalogue.json').write_text(json.dumps({'version':1,'models':public},ensure_ascii=False,indent=2),encoding='utf-8')
    (args.output/'preparation-report.json').write_text(json.dumps({'groups':len(todo),'prepared':len(prepared),'errors':failures},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'prepared':len(prepared),'deferred':len(failures)}),flush=True)


if __name__=='__main__':main()
