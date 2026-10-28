"""Build private Live2D library packages from the owner's approved Drive folder.

Run on the owner's PC, never on a tester's device. This prepares local packages;
it does not change Drive permissions or upload/publish anything to the internet.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor,as_completed

if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from model_import import import_package, MAX_BYTES, safe_path
from model_library_previews import live2d_preview

APPROVED_LIVE2D_FOLDER = '1IxXw-fjPVnl6vPAvM6DAcyzRYoAhiJLT'
ASSETS = {'.json', '.moc3', '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.txt', '.md', '.pdf', '.mtn', '.wav', '.mp3', '.ogg'}


class Drive:
    def __init__(self, headers):
        self.headers = headers
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        self.session=requests.Session()
        self.session.mount('https://',HTTPAdapter(max_retries=Retry(total=3,backoff_factor=1,
            status_forcelist=(429,500,502,503,504),allowed_methods=('GET',)),pool_maxsize=16))

    def children(self, identifier):
        if not re.fullmatch('[A-Za-z0-9_-]{1,200}', identifier):
            raise ValueError('Invalid Drive folder ID.')
        token = None
        while True:
            response = self.session.get('https://www.googleapis.com/drive/v3/files', headers=self.headers,
                params={'q': "'" + identifier + "' in parents and trashed = false", 'pageSize': 1000,
                        'pageToken': token, 'fields': 'nextPageToken,files(id,name,mimeType,size,md5Checksum)'},
                timeout=(8, 60), allow_redirects=False)
            if response.status_code != 200:
                raise ValueError('Drive listing was refused. Enable the Drive API and authorize owner read access.')
            data = response.json()
            yield from data.get('files', [])
            token = data.get('nextPageToken')
            if not token:
                break

    def download_tree(self, identifier, destination, budget=None, depth=0):
        if depth > 20:
            raise ValueError('Too many nested model folders.')
        budget = budget if budget is not None else [0, 0]
        seen = {}
        for item in self.children(identifier):
            name = item['name']
            if item['mimeType']!='application/vnd.google-apps.folder' and Path(name).suffix.lower() not in ASSETS:
                continue
            relative = safe_path(name)
            if len(relative.parts) != 1 or not relative.name:
                raise ValueError('A Drive folder contains unsafe or duplicate file names.')
            key=relative.name.casefold()
            if key in seen:
                old=seen[key]
                if (item.get('md5Checksum') and old.get('md5Checksum')==item['md5Checksum']
                        and old.get('size')==item.get('size')):continue
                raise ValueError('A Drive folder contains conflicting duplicate file names.')
            seen[key]=item
            target = destination / relative
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                target.mkdir()
                self.download_tree(item['id'], target, budget, depth + 1)
                continue
            if target.suffix.lower() not in ASSETS:
                continue  # No executable, editor project, credential or unrelated files.
            budget[1] += 1
            if budget[1] > 5000:
                raise ValueError('Model exceeds 5,000 runtime files.')
            if int(item.get('size', 0)) + budget[0] > MAX_BYTES:
                raise ValueError('Model exceeds 512 MB.')
            with self.session.get('https://www.googleapis.com/drive/v3/files/' + item['id'],
                    params={'alt': 'media'}, headers=self.headers, stream=True,
                    timeout=(8, 120), allow_redirects=False) as response:
                if response.status_code != 200:
                    raise ValueError('A model file could not be downloaded from Drive.')
                with target.open('wb') as output:
                    for chunk in response.iter_content(65536):
                        budget[0] += len(chunk)
                        if budget[0] > MAX_BYTES:
                            raise ValueError('Model exceeds 512 MB.')
                        output.write(chunk)


def complete_descriptor(folder):
    """Rebuild an omitted descriptor only when its MOC and texture directory are unambiguous."""
    if list(folder.rglob('*.model3.json')):return
    models=list(folder.rglob('*.moc3'))
    if len(models)!=1:return
    model=models[0]
    directories=[p for p in model.parent.iterdir() if p.is_dir() and
                 (p.name.startswith(model.stem+'.') or p.name.lower() in ('textures','texture'))]
    if len(directories)!=1:return
    textures=sorted(p for p in directories[0].rglob('*.png') if p.is_file())
    if not textures:return
    relative=lambda p:p.relative_to(model.parent).as_posix()
    references={'Moc':model.name,'Textures':[relative(p) for p in textures]}
    expressions=sorted(model.parent.rglob('*.exp3.json'))
    if expressions:references['Expressions']=[{'Name':p.name.removesuffix('.exp3.json'),'File':relative(p)} for p in expressions]
    motions=sorted(model.parent.rglob('*.motion3.json'))
    if motions:references['Motions']={'Idle':[{'File':relative(p)} for p in motions]}
    physics=list(model.parent.glob('*.physics3.json'))
    if len(physics)==1:references['Physics']=relative(physics[0])
    (model.parent/(model.stem+'.model3.json')).write_text(json.dumps({'Version':3,'FileReferences':references},ensure_ascii=False,indent=2),encoding='utf-8')


def package_folder(folder, name, identifier, output):
    """Validate in a temporary import library before admitting any package."""
    complete_descriptor(folder)
    files = sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in ASSETS)
    if not files or any(p.is_symlink() or not p.resolve().is_relative_to(folder.resolve()) for p in files):
        raise ValueError('Missing runtime assets or linked files in model package.')
    if len(files) > 5000 or sum(p.stat().st_size for p in files) > MAX_BYTES:
        raise ValueError('Model exceeds 512 MB or 5,000 files.')
    with tempfile.TemporaryDirectory(prefix='sakura-library-validation-') as validation:
        import_package(validation, [(p.relative_to(folder).as_posix(), p.read_bytes()) for p in files], 'live2d')
    target = output / (identifier + '.zip')
    temporary = output / (identifier + '.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in files:
                archive.write(path, path.relative_to(folder).as_posix())
        if temporary.stat().st_size > MAX_BYTES:
            raise ValueError('Compressed model exceeds 512 MB.')
        with temporary.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    preview=live2d_preview(folder,output/(identifier+'.webp'))
    return {'id': identifier, 'name': name, 'format': 'live2d', 'bytes': target.stat().st_size,'preview':preview,
            'sha256': digest, 'version': digest[:12], 'mobile_compatible': len(list(folder.rglob('*.model3.json'))) == 1}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--owner-google-connection', action='store_true', help='Use this PC owner Google connection; never copy it to the service or app.')
    parser.add_argument('--inventory-only', action='store_true')
    parser.add_argument('--workspace-credentials',type=Path,help='Owner Workspace MCP credential file; never copied to output.')
    parser.add_argument('--workers',type=int,default=4,choices=range(1,9))
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    if sys.platform=='win32':
        import msvcrt
        task_lock=(args.output/'prepare.lock').open('a+b');task_lock.seek(0);task_lock.write(b'1');task_lock.flush();task_lock.seek(0)
        try:msvcrt.locking(task_lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            print('Another preparation pass is running.');return 2
    access = os.environ.get('SAKURA_LIBRARY_DRIVE_ACCESS_TOKEN', '')
    if args.workspace_credentials:
        saved=json.loads(args.workspace_credentials.read_text(encoding='utf-8'))
        response=requests.post('https://oauth2.googleapis.com/token',data={
            'client_id':saved['client_id'],'client_secret':saved['client_secret'],
            'refresh_token':saved['refresh_token'],'grant_type':'refresh_token'},timeout=(8,25))
        if response.status_code!=200:raise ValueError('Owner Workspace authorization needs reconnecting.')
        headers={'Authorization':'Bearer '+response.json()['access_token']}
    elif args.owner_google_connection:
        from agent_calendar import google_calendar
        _, headers = google_calendar._auth()
    elif access:
        headers = {'Authorization': 'Bearer ' + access}
    else:
        parser.error('Owner Drive authorization is needed. Use --owner-google-connection or SAKURA_LIBRARY_DRIVE_ACCESS_TOKEN. Do not send credentials in chat.')
    drive = Drive(headers)
    folders = sorted((f for f in drive.children(APPROVED_LIVE2D_FOLDER) if f['mimeType'] == 'application/vnd.google-apps.folder'), key=lambda f: f['name'].casefold())
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'source_folder': APPROVED_LIVE2D_FOLDER, 'folders': [{'id': f['id'], 'name': f['name']} for f in folders], 'errors': []}
    entries = []
    progress=args.output/'prepared-models.json'
    try:prepared=json.loads(progress.read_text(encoding='utf-8'))
    except (OSError,ValueError):prepared={}
    if not args.inventory_only:
        def prepare(folder):
            identifier = 'live2d-' + hashlib.sha256(folder['id'].encode()).hexdigest()[:24]
            print('Preparing: '+folder['name'], flush=True)
            try:
                kept=prepared.get(identifier)
                package=args.output/(identifier+'.zip')
                if kept and package.is_file() and package.stat().st_size==kept.get('bytes'):
                    return kept,None
                with tempfile.TemporaryDirectory(prefix='sakura-drive-model-') as temporary:
                    stage = Path(temporary)
                    drive.download_tree(folder['id'], stage)
                    return package_folder(stage, folder['name'], identifier, args.output),None
            except (ValueError, OSError, requests.RequestException) as exc:
                # No owner tokens or request headers are recorded in reports.
                return None,{'name': folder['name'], 'error': str(exc) if isinstance(exc, ValueError) else 'Storage or network error.'}
        with ThreadPoolExecutor(max_workers=args.workers) as workers:
            jobs=[workers.submit(prepare,folder) for folder in folders]
            for job in as_completed(jobs):
                entry,error=job.result()
                if entry:
                    entries.append(entry);prepared[entry['id']]=entry
                    draft=progress.with_suffix('.tmp');draft.write_text(json.dumps(prepared,ensure_ascii=False,indent=2),encoding='utf-8');draft.replace(progress)
                if error:report['errors'].append(error)
                (args.output/'preparation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                print(f'Completed {len(entries)+len(report["errors"])}/{len(folders)}; packages {len(entries)}, errors {len(report["errors"])}',flush=True)
        # Atomic catalogue update: a reader never receives half-written JSON.
        draft = args.output / 'catalogue.tmp'
        draft.write_text(json.dumps({'version': 1, 'models': entries}, ensure_ascii=False, indent=2), encoding='utf-8')
        draft.replace(args.output / 'catalogue.json')
    (args.output / 'preparation-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'folders': len(folders), 'prepared': len(entries), 'errors': len(report['errors']), 'published_online': False}))
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
