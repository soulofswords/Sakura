"""Recover exact missing PNG textures from matching local PMX originals.

Requires the owner's texture-reference audit. Never overwrites a Jio object.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile
from urllib.parse import urlencode

def main():
    sys.stdout.reconfigure(encoding='utf-8');root=Path(__file__).resolve().parents[1];out=root.parent/'private-model-library-pmx'
    spec=importlib.util.spec_from_file_location('jio_transfer',Path(__file__).with_name('upload-library-jio.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    work=out/'texture-repairs';work.mkdir(exist_ok=True)
    temporary=tempfile.TemporaryDirectory(prefix='transfer-',dir=work)
    transfer=module.JioUploader(temporary.name);api=transfer.api;owner=transfer.connection
    entries=json.loads((out/'prepared-models.json').read_text(encoding='utf-8'))
    issues=json.loads((out/'pmx-required-textures.json').read_text(encoding='utf-8'));seen=set();fixed=[];affected=set();listing_cache={}
    def children(key):
        if key not in listing_cache:
            _,data=transfer.request('GET',api+'/nms/metadata?'+urlencode({'limit':2000,'folderKey':key,'sort':'+objectName'}))
            if data.get('nextLink'):raise ValueError('Repair folder needs complete pagination.')
            listing_cache[key]=data['objects']
        return listing_cache[key]
    def folder(key,name):
        matches=[x for x in children(key) if x.get('objectName')==name and x.get('objectType')=='FR']
        if not matches:
            _,created=transfer.request('POST',api+'/nms/folders',json_body={'objectName':name,'parentObjectKey':key,'sourceName':'DRIVE'})
            if created.get('objectName')!=name or created.get('parentObjectKey')!=key:raise ValueError('Repair folder could not be verified.')
            children(key).append(created);matches=[created]
        if len(matches)!=1:raise ValueError('Repair folder is ambiguous.')
        return matches[0]['objectKey']
    for issue in issues:
        if not issue['local_original_exists']:continue
        entry=entries[issue['id']];relative=Path(entry['preview_model'].removeprefix('pmx/'));model=root/'models/pmx'/relative
        mirrored=out/'jio-source'/relative
        if model.read_bytes()!=mirrored.read_bytes():raise ValueError('Local PMX differs from the uploaded model. No guessed texture used.')
        asset=(model.parent/issue['texture']).resolve();base=(root/'models/pmx').resolve()
        if asset.suffix.lower()!='.png' or not asset.is_relative_to(base):continue
        relative_asset=asset.relative_to(base);affected.add(issue['id'])
        if relative_asset.as_posix() in seen:continue
        seen.add(relative_asset.as_posix());key=owner.session['rootFolderKey']
        for part in ['PMX',*relative_asset.parts[:-1]]:key=folder(key,part)
        transfer.folder=key;transfer.remote={x['objectName']:[x] for x in children(key) if x.get('objectType')!='FR'};transfer.assets={}
        # Jio can deduplicate equal images under an existing, different name.
        # Wrap missing filenames so every PMX reference survives intact.
        digest=hashlib.sha256(asset.name.encode()+b'\0'+asset.read_bytes()).hexdigest()
        upload=work/('Sakura-original-textures-'+digest[:16]+'.zip')
        with zipfile.ZipFile(upload,'w',zipfile.ZIP_DEFLATED) as archive:archive.write(asset,asset.name)
        try:receipt=transfer.upload_file(upload)
        except module.UploadError:
            # A provider extension rewrite is diagnosed without printing its URL.
            transfer.remote=transfer.list_remote()
            print('Texture destination check: '+json.dumps({'expected':upload.name,'stored_names':list(transfer.remote)},ensure_ascii=False),flush=True)
            raise
        destination=out/'jio-source'/relative_asset;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(asset,destination)
        fixed.append({'path':relative_asset.as_posix(),'sha256':hashlib.sha256(asset.read_bytes()).hexdigest(),'verified':receipt['verified'],'stored_as':upload.name})
        (out/'jio-texture-repairs.json').write_text(json.dumps({'files':fixed,'affected_models':sorted(affected)},ensure_ascii=False,indent=2),encoding='utf-8')
        print('Verified missing texture: '+relative_asset.as_posix(),flush=True)
    print(json.dumps({'repaired_files':len(fixed),'affected_models':len(affected)}),flush=True)
    temporary.cleanup()

if __name__=='__main__':main()
