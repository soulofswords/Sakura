"""Repair only missing files identified by a completed read-only Jio audit."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import threading
import zipfile
from urllib.parse import urlencode, urlsplit, quote

from jio_library_owner import JioConnection, REGIONS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    report = json.loads(args.audit.read_text(encoding='utf-8'))
    local = Path(report['localPath']).resolve()
    prefix = report['remotePath'].split('/')
    if report.get('sizeMismatches') or report.get('hashMismatches') or report.get('duplicatePaths'):
        raise ValueError('Resolve audit conflicts before automatically repairing missing files.')
    spec = importlib.util.spec_from_file_location('jio_transfer', Path(__file__).with_name('upload-library-jio.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    owner = JioConnection()
    owner.configure()
    saved = owner.store.load()
    owner.session = saved['session']
    owner.destination = saved.get('destination')
    region = REGIONS[owner.session['dcGroupCode']]
    origin = f'https://{region}-api.jioaicloud.com'

    def listing(key):
        value = owner.request('GET', origin + '/nms/metadata?' + urlencode({
            'limit': 2000, 'folderKey': key, 'sort': '+objectName'}), authenticated=True)
        if value.get('nextLink'):
            raise ValueError('Parent folder needs pagination; refusing a partial destination lookup.')
        return value['objects']

    cache = {(): owner.session['rootFolderKey']}

    def folder(parts):
        parts = tuple(parts)
        if parts not in cache:
            parent = folder(parts[:-1])
            matches = [x for x in listing(parent) if x.get('objectType') == 'FR' and x.get('objectName') == parts[-1]]
            if len(matches) != 1:
                raise ValueError('Designated destination is missing or ambiguous.')
            cache[parts] = matches[0]['objectKey']
        return cache[parts]

    repaired = []
    archived = set()
    details = {item['path']: item['bytes'] for item in report['missingFileDetails']}
    for relative in report['missing']:
        if relative in archived:
            continue
        components = relative.split('/')
        source = local.joinpath(*components).resolve()
        if local not in source.parents or not source.is_file() or source.stat().st_size != details[relative]:
            raise ValueError('Local audit source changed or leaves its root folder.')
        parent = folder(prefix + components[:-1])
        transfer = module.JioUploader.__new__(module.JioUploader)
        transfer.directory = args.audit.parent
        transfer.connection = owner
        transfer.folder = parent
        transfer.user_id = owner.session['userId']
        transfer.region = region
        transfer.api = origin
        transfer.upload_api = f'https://{region}-upload.jioaicloud.com'
        transfer.download_api = f'https://{region}-dl.jioaicloud.com'
        transfer.allowed_hosts = {urlsplit(x).hostname for x in (origin, transfer.upload_api, transfer.download_api, module.SECURITY)}
        transfer.auth_lock = threading.RLock()
        transfer.ledger_lock = threading.RLock()
        transfer.thread_local = threading.local()
        transfer.ledger_path = args.audit.parent / ('jio-pmx-repair-' + module.hashlib.sha256(parent.encode()).hexdigest()[:12] + '.json')
        try:
            value = json.loads(transfer.ledger_path.read_text(encoding='utf-8'))
            if value['folderKey'] != parent or value['userId'] != owner.session['userId']:
                raise ValueError('Repair checkpoint account or folder mismatch.')
            transfer.assets = value['assets']
        except FileNotFoundError:
            transfer.assets = {}
        transfer.remote = transfer.list_remote()
        sha = module.digest_file(source)
        current = transfer.remote.get(source.name, [])
        if len(current) > 1:
            raise ValueError('Duplicate intended filenames; no repair attempted.')
        if current:
            metadata = current[0]
        else:
            # Jio can infer image format and change .tga to .png, even when
            # name and multipart filename both specify the original extension.
            inferred = source.stem + '.png'
            alternate = transfer.remote.get(inferred, []) if source.suffix.casefold() == '.tga' else []
            if len(alternate) > 1:
                raise ValueError('Ambiguous provider-renamed image.')
            if alternate:
                metadata = alternate[0]
                transfer.verify(metadata['objectKey'], source.stat().st_size, sha)
            else:
                info = {'name': source.name, 'size': source.stat().st_size,
                        'hash': module.digest_file(source, 'md5'), 'folderKey': parent}

                def factory():
                    opened = source.open('rb')
                    return {'metadataString': json.dumps(info)}, opened, {'file': (source.name, opened, 'application/octet-stream')}

                status, metadata = transfer.request('POST', transfer.upload_api + '/upload/files', files_factory=factory)
                if status != 201 or metadata.get('parentObjectKey') != parent or not metadata.get('objectKey'):
                    raise ValueError('Jio did not confirm a file in the intended parent folder.')
            transfer.verify(metadata['objectKey'], source.stat().st_size, sha)
            if metadata.get('objectName') != source.name:
                before = metadata.get('objectName')
                if source.suffix.casefold() != '.tga' or before != inferred:
                    raise ValueError('Unexpected provider filename. No rename attempted.')
                renamed = {**metadata, 'objectName': source.name}
                _, response = transfer.request('PUT', origin + '/nms/metadata/1.0', json_body={
                    'objects': [{'correlationId': owner.session['userId'], 'operation': 'RENAME', 'object': renamed}]})
                if response.get('unprocessed'):
                    errors = [{'code': entry.get('object', {}).get('errorCode'),
                               'message': entry.get('object', {}).get('errorMessage')}
                              for entry in response['unprocessed']]
                    (args.audit.parent / 'jio-pmx-rename-error.json').write_text(json.dumps(errors), encoding='utf-8')
                    # Personal Jio storage rejects this extension even though
                    # it accepts the PNG bytes. Archive preserves exact names
                    # and bytes without modifying the model's texture refs.
                    if not all(item.get('code') == 'NMSOM0106' for item in errors):
                        raise ValueError('Jio could not restore the required model texture filename.')
                    group = [name for name in report['missing'] if name.rsplit('/', 1)[0] == relative.rsplit('/', 1)[0]
                             and Path(name).suffix.casefold() == '.tga']
                    archive = args.audit.parent / 'Sakura-original-TGA-textures.zip'
                    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as package:
                        for name in group:
                            candidate = local.joinpath(*name.split('/')).resolve()
                            if local not in candidate.parents or candidate.stat().st_size != details[name]:
                                raise ValueError('Archive source changed since audit.')
                            package.write(candidate, arcname=candidate.name)
                    archive_receipt = transfer.upload_file(archive)
                    for name in group:
                        repaired.append({'path': name, 'bytes': details[name], 'verified': True,
                                         'storedInArchive': '/'.join(prefix + components[:-1] + [archive.name]),
                                         'archiveEntry': Path(name).name})
                        archived.add(name)
                    # Undo only the provider-renamed artifact created by this
                    # repair. The source audit proved this name did not exist.
                    transfer.request('PUT', origin + '/nms/metadata/trash',
                                     json_body={'objectKeys': [metadata['objectKey']]})
                    args.audit.with_name('jio-pmx-repair-report.json').write_text(
                        json.dumps(repaired, ensure_ascii=False, indent=2), encoding='utf-8')
                    print(json.dumps({'archivedOriginalFiles': len(group), 'archiveDownloadVerified': archive_receipt['verified']}, ensure_ascii=True), flush=True)
                    continue
                metadata = owner.request('GET', origin + '/nms/metadata/' + quote(metadata['objectKey'], safe='') + '/info', authenticated=True)
        if metadata.get('objectName') != source.name or metadata.get('parentObjectKey') != parent:
            raise ValueError('Repaired filename or parent did not verify.')
        transfer.verify(metadata['objectKey'], source.stat().st_size, sha)
        receipt = {'objectKey': metadata['objectKey'], 'bytes': source.stat().st_size, 'sha256': sha,
                   'md5': module.digest_file(source, 'md5'), 'verified': True}
        transfer.checkpoint(source.name, receipt)
        repaired.append({'path': relative, 'bytes': receipt['bytes'], 'sha256': sha, 'verified': True})
        output = args.audit.with_name('jio-pmx-repair-report.json')
        output.write_text(json.dumps(repaired, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'repaired': relative, 'bytes': receipt['bytes'], 'downloadVerified': True}, ensure_ascii=True), flush=True)
    print(json.dumps({'repairedFiles': len(repaired), 'allVerified': True}), flush=True)


if __name__ == '__main__':
    main()
