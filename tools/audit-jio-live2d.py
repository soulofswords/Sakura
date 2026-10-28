"""Read-only source-folder verification against the published Live2D inventory."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import threading
from urllib.parse import urlencode

from jio_library_owner import JioConnection, REGIONS, private_directory


def main():
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('publisher',root/'tools/publish-model-library.py')
    publisher=importlib.util.module_from_spec(spec);spec.loader.exec_module(publisher)
    owner=JioConnection();owner.resume();origin='https://'+REGIONS[owner.session['dcGroupCode']]+'-api.jioaicloud.com'
    local=threading.local()
    def listing(key):
        if not hasattr(local,'owner'):
            local.owner=JioConnection(store=owner.store);local.owner.session=owner.session;local.owner.headers=owner.headers
        url=origin+'/nms/metadata?'+urlencode({'limit':2000,'folderKey':key,'sort':'+objectName'});items=[];seen=set()
        for _ in range(100):
            if url in seen or not url.startswith(origin+'/nms/metadata'):raise ValueError('Invalid inventory pagination.')
            seen.add(url);data=local.owner.request('GET',url,authenticated=True);items.extend(data['objects'])
            link=data.get('nextLink')
            if not link:return items
            url=origin+link if isinstance(link,str) and link.startswith('/') and not link.startswith('//') else link
        raise ValueError('Too many inventory pages.')
    roots=[x for x in listing(owner.session['rootFolderKey']) if x.get('objectType')=='FR' and str(x.get('objectName','')).casefold()=='live2d']
    if len(roots)!=1:raise ValueError('Live2D source folder missing or ambiguous.')
    folders=[x for x in listing(roots[0]['objectKey']) if x.get('objectType')=='FR' and str(x.get('objectName','')).casefold()!='sakura library packages']
    directory=private_directory();saved=json.loads((directory/'jio-source-fingerprints.json').read_text(encoding='utf-8'))
    def one(folder):
        identifier='live2d-'+hashlib.sha256(('jio:'+folder['objectKey']).encode()).hexdigest()[:24]
        files={};queue=[(folder['objectKey'],'')];keys=set()
        while queue:
            key,prefix=queue.pop()
            if key in keys or len(Path(prefix).parts)>20:raise ValueError('Source folder cycle or depth limit.')
            keys.add(key)
            for item in listing(key):
                name=publisher.safe_path(item['objectName'])
                if len(name.parts)!=1:raise ValueError('Unsafe source name.')
                relative=(Path(prefix)/name).as_posix()
                if item.get('objectType')=='FR':queue.append((item['objectKey'],relative))
                elif name.suffix.casefold() in publisher.ASSETS:
                    if relative in files:raise ValueError('Duplicate source file.')
                    files[relative]=item
        signature=hashlib.sha256(json.dumps(sorted((k,v.get('hash'),v.get('sizeInBytes'),v.get('lastModifiedDate')) for k,v in files.items())).encode()).hexdigest()
        return {'id':identifier,'name':folder['objectName'],'files':len(files),'matches':saved.get(identifier)==signature}
    with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(one,folders))
    seen={x['id'] for x in rows};report={'folders':len(rows),'files':sum(x['files'] for x in rows),'changed_or_new':[x['name'] for x in rows if not x['matches']], 'missing_previously_seen':sorted(set(saved)-seen)}
    (directory/'live2d-source-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
