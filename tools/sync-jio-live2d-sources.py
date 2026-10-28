"""Prepare newly uploaded folders under Jio/live2d, with real portrait previews.

Existing generated ZIPs/images are ignored. Original owner folders are read only.
"""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from urllib.parse import quote,urlencode
import requests
from jio_library_owner import JioConnection,REGIONS,private_directory,account_id

def main(root=None):
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    out=private_directory(root=root);out.mkdir(exist_ok=True)
    spec=importlib.util.spec_from_file_location('live2d_publisher',root/'tools/publish-model-library.py')
    publisher=importlib.util.module_from_spec(spec);spec.loader.exec_module(publisher)
    owner=JioConnection();owner.resume();region=REGIONS[owner.session['dcGroupCode']];api='https://'+region+'-api.jioaicloud.com'
    def listing(key):
        url=api+'/nms/metadata?'+urlencode({'limit':2000,'folderKey':key,'sort':'+objectName'});items=[];seen=set()
        for _ in range(100):
            if url in seen or not url.startswith(api+'/nms/metadata'):raise ValueError('Unexpected source listing.')
            seen.add(url);result=owner.request('GET',url,authenticated=True);items.extend(result['objects'])
            link=result.get('nextLink')
            if not link:return items
            url=api+link if isinstance(link,str) and link.startswith('/') and not link.startswith('//') else link
        raise ValueError('Too many source pages.')
    roots=[x for x in listing(owner.session['rootFolderKey']) if x.get('objectType')=='FR' and str(x.get('objectName','')).casefold()=='live2d']
    if len(roots)!=1:raise ValueError('Live2D source folder is missing or ambiguous.')
    folders=[x for x in listing(roots[0]['objectKey']) if x.get('objectType')=='FR' and str(x.get('objectName','')).casefold()!='sakura library packages']
    checkpoint=out/'prepared-models.json';prepared=json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.exists() else {}
    hashes_path=out/'jio-source-fingerprints.json';hashes=json.loads(hashes_path.read_text()) if hashes_path.exists() else {}
    failures=[];created=0
    for folder in folders:
        identifier=('' if account_id()=='primary' else account_id()+'-')+'live2d-'+hashlib.sha256(('jio:'+folder['objectKey']).encode()).hexdigest()[:24]
        try:
            files={};queue=[(folder['objectKey'],'')]
            while queue:
                key,prefix=queue.pop()
                if len(Path(prefix).parts)>20:raise ValueError('Too many nested model folders.')
                seen_names=set()
                for item in listing(key):
                    name=publisher.safe_path(item['objectName'])
                    if len(name.parts)!=1:raise ValueError('Unsafe source name.')
                    if name.name.casefold() in seen_names:raise ValueError('Conflicting source names on Windows.')
                    seen_names.add(name.name.casefold())
                    relative=(Path(prefix)/name).as_posix()
                    if item.get('objectType')=='FR':queue.append((item['objectKey'],relative))
                    elif name.suffix.casefold() in publisher.ASSETS:
                        if relative in files:raise ValueError('Duplicate runtime asset.')
                        files[relative]=item
            if len(files)>5000 or sum(int(x.get('sizeInBytes',0)) for x in files.values())>publisher.MAX_BYTES:raise ValueError('Live2D folder exceeds import limits.')
            signature=hashlib.sha256(json.dumps(sorted((k,v.get('hash'),v.get('sizeInBytes'),v.get('lastModifiedDate')) for k,v in files.items())).encode()).hexdigest()
            if hashes.get(identifier)==signature and identifier in prepared and (out/(identifier+'.zip')).is_file():continue
            mirror=out/'jio-source'/identifier;mirror.mkdir(parents=True,exist_ok=True)
            for old in mirror.rglob('*'):
                if old.is_file() and old.relative_to(mirror).as_posix() not in files:old.unlink()
            with requests.Session() as http:
                for relative,item in files.items():
                    target=mirror/relative;expected=item.get('hash');size=int(item.get('sizeInBytes',0))
                    if target.is_symlink() or not target.resolve().is_relative_to(mirror.resolve()):raise ValueError('Linked source mirror entry.')
                    if not isinstance(expected,str) or len(expected)!=32:raise ValueError('Source checksum unavailable.')
                    if target.is_file() and target.stat().st_size==size:
                        with target.open('rb') as stream:
                            if hashlib.file_digest(stream,'md5').hexdigest()==expected.lower():continue
                    target.parent.mkdir(parents=True,exist_ok=True);temporary=target.with_suffix(target.suffix+'.download')
                    for attempt in range(4):
                        try:
                            headers={**owner.headers,'Authorization':'Basic '+base64.b64encode(owner.session['authToken']['accessToken'].encode()).decode(),'X-User-Id':owner.session['userId'],'X-Device-Key':owner.session['deviceKey']}
                            with http.get('https://'+region+'-dl.jioaicloud.com/download/files/'+quote(item['objectKey'],safe=''),headers=headers,timeout=(10,120),stream=True,allow_redirects=False) as response:
                                if response.status_code!=200:raise ValueError('Source download refused.')
                                count=0;digest=hashlib.md5()
                                with temporary.open('wb') as output:
                                    for chunk in response.iter_content(65536):
                                        count+=len(chunk)
                                        if count>size:raise ValueError('Source size mismatch.')
                                        digest.update(chunk);output.write(chunk)
                            if count!=size or digest.hexdigest()!=expected.lower():raise ValueError('Source checksum mismatch.')
                            temporary.replace(target);break
                        except (requests.RequestException,ValueError):
                            temporary.unlink(missing_ok=True)
                            if attempt==3:raise ValueError('Source transfer failed after retries.') from None
                            time.sleep(2**attempt)
            entry=publisher.package_folder(mirror,folder['objectName'],identifier,out)
            prepared[identifier]=entry;hashes[identifier]=signature;created+=1
            checkpoint.write_text(json.dumps(prepared,ensure_ascii=False,indent=2),encoding='utf-8');hashes_path.write_text(json.dumps(hashes,indent=2))
            print('Prepared Live2D: '+folder['objectName'],flush=True)
        except (ValueError,OSError,requests.RequestException) as exc:
            failures.append({'folder':folder['objectName'],'error':str(exc) if isinstance(exc,ValueError) else type(exc).__name__})
    (out/'catalogue.json').write_text(json.dumps({'version':1,'models':list(prepared.values())},ensure_ascii=False,indent=2),encoding='utf-8')
    report={'source_folders':len(folders),'new_or_updated':created,'errors':failures}
    (out/'jio-live2d-sync-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
    return 2 if failures else 0

if __name__=='__main__':raise SystemExit(main())
