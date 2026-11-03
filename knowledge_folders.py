"""Explicitly approved folder indexes. Never watches or crawls the entire PC."""
import fnmatch
import hashlib
import json
import os
from pathlib import Path
from atomic_state import atomic_text,state_lock
from sandbox_mount_policy import BLOCKED

TEXT={'.txt','.md','.csv','.json','.py','.js','.ts','.html','.css','.rst'}
SKIP={'.git','.ssh','.aws','.gnupg','.kube','node_modules','venv','.venv','__pycache__','desktop-profile'}


def manifest(folder):
    original=Path(folder).expanduser();root=original.resolve(strict=True)
    if not root.is_dir() or root==Path(root.anchor) or root==Path.home().resolve():raise ValueError('Choose a dedicated document folder, not a drive or home directory.')
    if str(original.absolute()).casefold()!=str(root).casefold() or any(part.startswith('.') for part in root.parts if part not in (root.anchor,)):
        raise ValueError('Choose a real, non-hidden document folder, without links.')
    rows=[];total=0;visited=0
    for current,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=sorted(d for d in dirs if not d.startswith('.') and d.casefold() not in SKIP and not (Path(current)/d).is_symlink() and not (Path(current)/d).is_junction())
        for name in sorted(files):
            visited+=1
            if visited>5000:raise ValueError('Choose a smaller folder (scan limit 5,000 files).')
            path=Path(current)/name;relative=path.relative_to(root).as_posix()
            if name.startswith('.') or path.suffix.casefold() not in TEXT or path.is_symlink() or path.is_junction():continue
            if any(fnmatch.fnmatchcase(relative.casefold(),p) or fnmatch.fnmatchcase(name.casefold(),p) for p in BLOCKED):continue
            if path.resolve()!=path or any(p.casefold() in SKIP for p in path.relative_to(root).parts):continue
            size=path.stat().st_size
            if size>1_000_000:continue
            total+=size
            if len(rows)>=200 or total>10_000_000:raise ValueError('Limit: 200 text files / 10 MB per approved folder.')
            with path.open('rb') as handle:data=handle.read(1_000_001)
            if len(data)!=size:raise ValueError('File changed during folder review. Review again.')
            rows.append({'path':relative,'sha256':hashlib.sha256(data).hexdigest(),'bytes':size})
    info=root.stat()
    return {'root':str(root),'identity':[info.st_dev,info.st_ino],'files':rows,'bytes':total}


class FolderKnowledge:
    def __init__(self,path,knowledge):self.path=Path(path);self.knowledge=knowledge
    def folders(self):
        try:rows=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError):rows=[]
        return rows if isinstance(rows,list) else []
    def index(self,reviewed,semantic=False):
        current=manifest(reviewed['root'])
        if current!=reviewed:raise ValueError('Folder changed after review. Review it again.')
        root=Path(current['root']);indexed=[]
        for row in current['files']:
            path=root/row['path']
            if path.is_symlink() or path.is_junction() or path.resolve()!=path:raise ValueError('A file became a link. Review again.')
            with path.open('rb') as handle:data=handle.read(1_000_001)
            if len(data)!=row['bytes']:raise ValueError('File changed during indexing.')
            if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('File changed during indexing.')
            try:text=data.decode('utf-8-sig')
            except UnicodeDecodeError:continue
            if not text.strip():continue
            result=self.knowledge.index(root,row['path'],text)
            if semantic:result.update(self.knowledge.embed_source(root,row['path']))
            indexed.append(result)
        # Retire removed sources only after a successful pass; originals stay untouched.
        from contextlib import closing
        keep={row['path'] for row in current['files']}
        with closing(self.knowledge.connect()) as db,db:
            stale=[row[0] for row in db.execute('SELECT source FROM sources WHERE workspace=?',(str(root),)) if row[0] not in keep]
            for source in stale:
                for table in ('chunks','semantic_chunks','sources'):db.execute('DELETE FROM '+table+' WHERE workspace=? AND source=?',(str(root),source))
        with state_lock(self.path):
            items=[x for x in self.folders() if x['root']!=str(root)]
            if len(items)>=20:raise ValueError('Folder library is full (20). Remove an old folder first.')
            items.append({'root':str(root),'identity':current['identity'],'files':len(indexed),'semantic_requested':bool(semantic)})
            atomic_text(self.path,json.dumps(items))
        return {'ok':True,'folder':str(root),'indexed':len(indexed),'results':indexed}
    def search(self,query):
        results=[]
        for item in self.folders():
            root=Path(item['root'])
            try:info=root.stat()
            except OSError:continue
            if [info.st_dev,info.st_ino]!=item['identity'] or root.resolve()!=root:continue
            for row in self.knowledge.search(root,query)['results']:results.append({**row,'folder':str(root)})
        return {'ok':True,'results':results[:20],'warning':'Approved local indexes only; historical evidence. Reindex changed sources.'}
    def remove(self,root):
        with state_lock(self.path):
            items=self.folders();selected=next((x for x in items if x['root']==root),None)
            if not selected:raise ValueError('Choose an indexed folder.')
            self.knowledge.clear(root)
            atomic_text(self.path,json.dumps([x for x in items if x['root']!=root]))
        return {'ok':True}
