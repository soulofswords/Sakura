"""Owner PMX sync: read original Jio game folders, stage runtime assets privately.

Default is inventory only. --prepare downloads new/changed runtime assets into
a private mirror and validates packages. Original Jio/local model trees are
never overwritten. Run preview/upload/publication tools on this prepared mirror.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import importlib.util
import json
from pathlib import Path
import os
import sys
import time
import zipfile
from urllib.parse import urlencode,quote

from jio_library_owner import JioConnection,REGIONS,private_directory,account_id


def checked_relative(value):
    parts=value.split('/')
    if any(not x or x in ('.','..') or '\\' in x or ':' in x for x in parts):
        raise ValueError('Unsafe remote path.')
    return Path(*parts)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    args=parser.parse_args();sys.stdout.reconfigure(encoding='utf-8')
    root=Path(__file__).resolve().parents[1]
    out=private_directory('pmx')
    mirror=out/'jio-source';mirror.mkdir(parents=True,exist_ok=True)
    owner=JioConnection();owner.resume()
    region=REGIONS[owner.session['dcGroupCode']];api=f'https://{region}-api.jioaicloud.com'
    def listing(key):
        url=api+'/nms/metadata?'+urlencode({'limit':2000,'folderKey':key,'sort':'+objectName'})
        result=[];seen=set()
        for _ in range(100):
            if url in seen or not (url.startswith(api+'/nms/metadata?') or url.startswith(api+'/nms/metadata/')):raise ValueError('Unsafe pagination.')
            seen.add(url);data=owner.request('GET',url,authenticated=True);result.extend(data['objects'])
            link=data.get('nextLink')
            if not link:return result
            url=api+link if isinstance(link,str) and link.startswith('/') and not link.startswith('//') else link
        raise ValueError('Folder listing exceeded supported size.')
    matches=[x for x in listing(owner.session['rootFolderKey']) if x.get('objectName')=='PMX' and x.get('objectType')=='FR']
    if len(matches)!=1:raise ValueError('PMX source folder is missing or ambiguous.')
    top=listing(matches[0]['objectKey']);queue=[]
    categories=[x for x in top if x.get('objectType')=='FR' and str(x.get('objectName','')).casefold()!='sakura library packages']
    for item in categories:
        name=item.get('objectName','');checked_relative(name)
        queue.append((item['objectKey'],name))
    if not queue:raise ValueError('No model folders found inside PMX.')
    print('PMX source categories: '+', '.join(x['objectName'] for x in categories),flush=True)
    files={};folders=0
    with ThreadPoolExecutor(max_workers=4) as pool:
        while queue:
            futures={pool.submit(listing,key):prefix for key,prefix in queue};queue=[]
            for future in as_completed(futures):
                prefix=futures[future];folders+=1
                for item in future.result():
                    name=item.get('objectName','');checked_relative(name)
                    path=prefix+'/'+name
                    if item.get('objectType')=='FR':queue.append((item['objectKey'],path))
                    elif path in files:raise ValueError('Duplicate source path: '+path)
                    else:files[path]=item
            print(f'Inventoried {folders} folders, {len(files)} files.',flush=True)
    (out/'jio-source-inventory.json').write_text(json.dumps({'files':files,'folders':folders,'categories':[x['objectName'] for x in categories]},ensure_ascii=False,indent=2),encoding='utf-8')
    if not args.prepare:
        print('Inventory saved. Run with --prepare to build new packages. No model files changed.');return
    signature=hashlib.sha256(json.dumps(sorted((k,v.get('hash'),v.get('sizeInBytes'),v.get('lastModifiedDate')) for k,v in files.items())).encode()).hexdigest()
    signature_file=out/'jio-last-prepared-signature.txt'
    if signature_file.exists() and signature_file.read_text().strip()==signature and (out/'prepared-models.json').is_file():
        print('PMX source unchanged; existing validated packages and previews reused.',flush=True);return
    spec=importlib.util.spec_from_file_location('pmx_prepare',Path(__file__).with_name('prepare-jio-pmx-library.py'))
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    expected_paths=set(files)
    for archive in mirror.rglob('Sakura-original-*.zip'):
        if archive.relative_to(mirror).as_posix() in files:
            with zipfile.ZipFile(archive) as package:
                for member in package.infolist():
                    part=checked_relative(member.filename)
                    if len(part.parts)==1 and part.suffix.casefold() in {'.tga','.png','.jpg','.jpeg','.bmp','.dds','.gif','.sph','.spa','.txt','.md','.pdf'}:expected_paths.add((archive.parent/part).relative_to(mirror).as_posix())
    # This is a disposable mirror only. Removing a hardlink here never removes
    # its original local file; stale source assets must not enter new packages.
    for path in mirror.rglob('*'):
        if path.is_file() and path.relative_to(mirror).as_posix() not in expected_paths:
            if not path.resolve().is_relative_to(mirror.resolve()):raise ValueError('Linked private mirror entry.')
            path.unlink()
    # Hash-match alternate local folder layouts before downloading a second copy.
    by_size={}
    for source in (root/'models/pmx').rglob('*'):
        if source.is_file() and source.suffix.casefold() in builder.ASSETS:
            by_size.setdefault(source.stat().st_size,[]).append(source)
    import base64,requests,threading
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    thread_local=threading.local();hashes={};hash_lock=threading.Lock()
    def md5(path):
        with hash_lock:cached=hashes.get(str(path))
        if cached:return cached
        with path.open('rb') as stream:value=hashlib.file_digest(stream,'md5').hexdigest()
        with hash_lock:hashes[str(path)]=value
        return value
    def download(pair):
        relative,item=pair
        part=checked_relative(relative);extension=part.suffix.casefold()
        is_repair_archive=part.name.startswith('Sakura-original-') and part.suffix.lower()=='.zip'
        if extension not in builder.ASSETS and not is_repair_archive:return
        target=mirror/part;size=int(item.get('sizeInBytes',0))
        if size<0 or size>512*1024*1024:raise ValueError('Source asset exceeds limits.')
        expected=item.get('hash')
        if not isinstance(expected,str) or len(expected)!=32:
            info=owner.request('GET',api+'/nms/metadata/'+quote(item['objectKey'],safe='')+'/info',authenticated=True)
            expected=info.get('hash')
        if not isinstance(expected,str) or len(expected)!=32:raise ValueError('Source asset checksum unavailable.')
        def matches(path):
            return path.is_file() and path.stat().st_size==size and md5(path)==expected.lower()
        if matches(target):return
        target.parent.mkdir(parents=True,exist_ok=True)
        source=root/'models/pmx'/part
        candidates=[source,*sorted(by_size.get(size,[]),key=lambda p:p.name.casefold()!=part.name.casefold())]
        source=next((p for p in candidates if matches(p)),None)
        temporary=target.with_suffix(target.suffix+'.sakura-download')
        temporary.unlink(missing_ok=True)
        if source:
            try:os.link(source,temporary)
            except OSError:temporary.write_bytes(source.read_bytes())
        else:
            if not hasattr(thread_local,'http'):
                thread_local.http=requests.Session()
                thread_local.http.mount('https://',HTTPAdapter(max_retries=Retry(total=3,backoff_factor=1,status_forcelist=(429,500,502,503,504),allowed_methods=('GET',))))
            headers={**owner.headers,'Authorization':'Basic '+base64.b64encode(owner.session['authToken']['accessToken'].encode()).decode(),
                     'X-User-Id':owner.session['userId'],'X-Device-Key':owner.session['deviceKey']}
            url=f'https://{region}-dl.jioaicloud.com/download/files/'+quote(item['objectKey'],safe='')
            for attempt in range(4):
                try:
                    with thread_local.http.get(url,headers=headers,timeout=(10,120),stream=True,allow_redirects=False) as response:
                        if response.status_code!=200:raise ValueError('Source download refused; retry sync later.')
                        count=0
                        with temporary.open('wb') as output:
                            for chunk in response.iter_content(65536):
                                count+=len(chunk)
                                if count>size:raise ValueError('Source download exceeded metadata size.')
                                output.write(chunk)
                    with temporary.open('rb') as stream:valid=hashlib.file_digest(stream,'md5').hexdigest()==expected.lower()
                    if not valid:raise ValueError('Source checksum failed.')
                    break
                except (requests.RequestException,ValueError):
                    temporary.unlink(missing_ok=True)
                    if attempt==3:raise ValueError('Source download failed after retries: '+relative) from None
                    time.sleep(2**attempt)
        temporary.replace(target)
    failed=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs={pool.submit(download,pair):pair[0] for pair in files.items()}
        for count,future in enumerate(as_completed(jobs),1):
            try:future.result()
            except Exception as exc:failed.append({'path':jobs[future],'error':str(exc) if isinstance(exc,ValueError) else type(exc).__name__})
            if count%500==0:print(f'Checked/downloaded {count}/{len(files)} source assets.',flush=True)
    if failed:
        (out/'jio-source-download-errors.json').write_text(json.dumps(failed,ensure_ascii=False,indent=2),encoding='utf-8')
        raise ValueError(str(len(failed))+' source files could not be verified. Completed files kept for retry.')
    # Restore Jio's extension-preserving repair archives into the private mirror.
    # Never alter the originals or blindly extract archive paths.
    for archive in mirror.rglob('Sakura-original-*.zip'):
        with zipfile.ZipFile(archive) as package:
            if len(package.infolist())>100:raise ValueError('Repair archive is unexpectedly large.')
            for member in package.infolist():
                part=checked_relative(member.filename)
                if len(part.parts)!=1 or part.suffix.casefold() not in {'.tga','.png','.jpg','.jpeg','.bmp','.dds','.gif','.sph','.spa','.txt','.md','.pdf'} or member.file_size>100_000_000:raise ValueError('Unexpected repair archive member.')
                destination=archive.parent/part
                content=package.read(member)
                if destination.is_file() and destination.read_bytes()==content:continue
                temporary=destination.with_suffix('.sakura-restore');temporary.write_bytes(content);temporary.replace(destination)
    # Build into a fresh generation so files removed from the source cannot be
    # accidentally republished from a stale old prepared checkpoint.
    checkpoint=out/'prepared-models.json'
    previous=json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.exists() else {}
    prepared={};errors=[]
    for category,folder,selected in builder.variants(mirror):
        try:
            key,entry=builder.prepare(mirror,category,folder,out,previous,selected)
            entry['storage_account']=account_id()
            # Preserve existing generated rotating previews for unchanged ZIPs.
            old=previous.get(key,{})
            if old.get('sha256')==entry['sha256'] and (out/(key+'.webp')).is_file():entry['preview']=old.get('preview',False)
            prepared[key]=entry
        except ValueError as exc:errors.append({'folder':folder.relative_to(mirror).as_posix(),'error':str(exc)})
    temporary=checkpoint.with_suffix('.sync-tmp');temporary.write_text(json.dumps(prepared,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(checkpoint)
    (out/'jio-source-sync-report.json').write_text(json.dumps({'prepared':len(prepared),'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    signature_file.write_text(signature)
    print(json.dumps({'prepared':len(prepared),'excluded':len(errors),'mirror':str(mirror)}),flush=True)


if __name__=='__main__':main()
