"""Upload prepared library assets only to the owner's confirmed Jio folder.

Uses encrypted owner credentials, chunk checksums, verified downloads and a local
resume ledger. Never creates a public share link or changes source Drive files.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import threading
import time
from urllib.parse import quote, urlencode, urlsplit

import requests

from jio_library_owner import JioConnection, ConnectionError, REGIONS, SECURITY

# Jio's published web client allows chunks up to 20 MiB. Use 16 MiB to
# reduce round trips while keeping memory bounded for parallel uploads.
CHUNK = 16 * 1024 * 1024


class UploadError(ValueError):
    pass


def digest_file(path, algorithm='sha256'):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


class JioUploader:
    def __init__(self, directory, workers=3, remote_folder=None):
        self.directory = Path(directory)
        self.connection = JioConnection()
        self.connection.resume()
        if not self.connection.destination:
            raise UploadError('Confirm the Jio account and existing live2d folder before uploading.')
        self.folder = self.connection.destination['folderKey']
        self.user_id = self.connection.destination['userId']
        self.region = REGIONS[self.connection.session['dcGroupCode']]
        self.api = f'https://{self.region}-api.jioaicloud.com'
        self.upload_api = f'https://{self.region}-upload.jioaicloud.com'
        self.download_api = f'https://{self.region}-dl.jioaicloud.com'
        self.allowed_hosts = {urlsplit(url).hostname for url in (self.api, self.upload_api, self.download_api, SECURITY)}
        self.auth_lock = threading.RLock()
        self.ledger_lock = threading.RLock()
        self.thread_local = threading.local()
        self.workers = workers
        if remote_folder:
            # Explicit owner-selected root path. Only the final package folder
            # may be created; existing source character folders are never moved.
            key=self.connection.session['rootFolderKey']
            parts=remote_folder.strip('/').split('/')
            if parts!=['PMX','Sakura library packages']:
                raise UploadError('Choose the PMX / Sakura library packages destination.')
            for index,name in enumerate(parts):
                url=self.api+'/nms/metadata?'+urlencode({'limit':2000,'folderKey':key,'sort':'+objectName'})
                _,listing=self.request('GET',url)
                if listing.get('nextLink'):raise UploadError('Destination needs a complete folder listing.')
                matches=[x for x in listing.get('objects',[]) if x.get('objectName')==name and x.get('objectType')=='FR']
                if not matches and index==1:
                    _,created=self.request('POST',self.api+'/nms/folders',json_body={'objectName':name,'parentObjectKey':key,'sourceName':'DRIVE'})
                    if created.get('objectName')!=name or created.get('parentObjectKey')!=key:raise UploadError('Could not verify the package folder.')
                    matches=[created]
                if len(matches)!=1:raise UploadError('Destination folder is missing or ambiguous.')
                key=matches[0]['objectKey']
            self.folder=key
        self.ledger_path = self.directory / 'jio-uploaded-assets.json'
        try:
            saved = json.loads(self.ledger_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            saved = {}
        if saved and (saved.get('folderKey') != self.folder or saved.get('userId') != self.user_id):
            raise UploadError('The saved upload ledger belongs to another account or folder. Nothing was uploaded.')
        self.assets = saved.get('assets', {})
        self.remote = self.list_remote()

    def http(self):
        if not hasattr(self.thread_local, 'session'):
            self.thread_local.session = requests.Session()
        return self.thread_local.session

    def headers(self):
        with self.auth_lock:
            session = self.connection.session
            return {**self.connection.headers,
                    'Authorization': 'Basic ' + base64.b64encode(session['authToken']['accessToken'].encode()).decode(),
                    'X-User-Id': session['userId'], 'X-Device-Key': session['deviceKey']}

    def refresh(self, previous_token):
        with self.auth_lock:
            current = self.connection.session['authToken']
            if current['accessToken'] != previous_token:
                return
            if not current.get('refreshToken'):
                raise UploadError('Jio login expired. Reconnect before resuming uploads.')
            value = self.connection.request('PUT', SECURITY + '/account/token/refresh',
                                           {'refreshToken': current['refreshToken'], 'deviceType': 'W','jToken':True,
                                            'isIdamOn':'true','isStaySignIn':True,'deviceInfo':{'model':'browser',
                                            'deviceName':'Web Device','type':'browser','isWebClient':True,
                                            'deviceKey':self.connection.session['deviceKey']}},
                                           authenticated=True)
            replacement = value.get('authToken', value)
            if not isinstance(replacement.get('accessToken'), str) or not replacement['accessToken']:
                raise UploadError('Jio did not refresh the login. Reconnect before resuming.')
            for key in ('accessToken', 'refreshToken', 'expiresIn'):
                if key in replacement:
                    current[key] = replacement[key]
            self.connection.store.save({'session': self.connection.session, 'destination': self.connection.destination})

    def request(self, method, url, *, raw=None, json_body=None, files_factory=None, extra=None, stream=False):
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname not in self.allowed_hosts
                or parsed.port not in (None, 443) or parsed.username or parsed.password or parsed.fragment):
            raise UploadError('Unexpected Jio service address. No credential was sent.')
        for attempt in range(2):
            with self.auth_lock:
                token = self.connection.session['authToken']['accessToken']
            headers = self.headers()
            headers.update(extra or {})
            if files_factory or stream:
                headers.pop('Content-Type', None)
            opened = None
            try:
                kwargs = {'headers': headers, 'timeout': (10, 180), 'allow_redirects': False, 'stream': True}
                if files_factory:
                    form, opened, files = files_factory()
                    multipart = requests.Request(method, url, data=form, files=files).prepare()
                    # File-like bodies let urllib3 write bounded TLS blocks.
                    # A multi-MiB bytes send can raise SSLWantWriteError on this
                    # Windows runtime while the uplink is under backpressure.
                    kwargs['headers']['Content-Type'] = multipart.headers['Content-Type']
                    kwargs['data'] = io.BytesIO(multipart.body)
                elif raw is not None:
                    kwargs['data'] = io.BytesIO(raw)
                elif json_body is not None:
                    kwargs['json'] = json_body
                response = self.http().request(method, url, **kwargs)
            finally:
                if opened:
                    opened.close()
            if response.status_code in (401, 403) and attempt == 0:
                response.close()
                self.refresh(token)
                continue
            if stream and response.status_code == 200:
                return response
            with response:
                chunks, length = [], 0
                for data in response.iter_content(65536):
                    length += len(data)
                    if length > 2_000_000:
                        raise UploadError('Jio returned an oversized transfer response.')
                    chunks.append(data)
                try:
                    result = json.loads(b''.join(chunks))
                except (ValueError, UnicodeError):
                    result = {}
                if not 200 <= response.status_code < 300:
                    code = result.get('code', '') if isinstance(result, dict) else ''
                    code = code if isinstance(code, str) and re.fullmatch(r'[A-Z0-9_-]{1,40}', code) else ''
                    raise UploadError(f'Jio transfer failed (HTTP {response.status_code}, {code or "no code"}).')
                if not isinstance(result, dict):
                    raise UploadError('Jio returned an invalid transfer response.')
                return response.status_code, result

    def list_remote(self):
        url = self.api + '/nms/metadata?' + urlencode({'limit': 300, 'folderKey': self.folder, 'sort': '+objectName'})
        result, seen = {}, set()
        for _ in range(100):
            if url in seen or not (url.startswith(self.api + '/nms/metadata?') or url.startswith(self.api + '/nms/metadata/')):
                raise UploadError('Invalid Jio folder pagination.')
            seen.add(url)
            _, data = self.request('GET', url)
            objects = data.get('objects')
            if not isinstance(objects, list):
                raise UploadError('Could not list the confirmed destination folder.')
            for item in objects:
                if isinstance(item, dict) and item.get('objectName') and item.get('objectKey'):
                    result.setdefault(item['objectName'], []).append(item)
            link = data.get('nextLink')
            if not link:
                return result
            if not isinstance(link, str):
                raise UploadError('Invalid Jio next-page address.')
            url = self.api + link if link.startswith('/') and not link.startswith('//') else link
        raise UploadError('Jio folder listing exceeded the supported page count.')

    def checkpoint(self, name, value):
        with self.ledger_lock:
            self.assets[name] = value
            content = {'folderKey': self.folder, 'userId': self.user_id, 'assets': self.assets}
            temporary = self.ledger_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(self.ledger_path)

    def verify(self, object_key, size, sha256):
        url = self.download_api + '/download/files/' + quote(object_key, safe='')
        response = self.request('GET', url, stream=True)
        with response:
            digest, total = hashlib.sha256(), 0
            for chunk in response.iter_content(1024 * 1024):
                total += len(chunk)
                if total > size:
                    raise UploadError('Jio returned more bytes than the prepared file.')
                digest.update(chunk)
        if total != size or digest.hexdigest() != sha256:
            raise UploadError('Downloaded Jio file did not match its prepared SHA256 and size.')

    def upload_file(self, path, expected_sha=None):
        size = path.stat().st_size
        sha = digest_file(path)
        if expected_sha and sha != expected_sha:
            raise UploadError('A local package no longer matches the validated catalogue.')
        md5 = digest_file(path, 'md5')
        old = self.assets.get(path.name)
        if old and old.get('verified') and old.get('sha256') == sha:
            candidates = self.remote.get(path.name, [])
            if any(item['objectKey'] == old.get('objectKey') and int(item.get('sizeInBytes', item.get('size', 0))) == size for item in candidates):
                return old
        candidates = self.remote.get(path.name, [])
        if candidates:
            if len(candidates) != 1:
                raise UploadError('Duplicate destination filenames prevent safe automatic resume.')
            metadata = candidates[0]
            if int(metadata.get('sizeInBytes', metadata.get('size', 0))) != size:
                raise UploadError('A different file already uses the prepared filename. It was not overwritten.')
            self.verify(metadata['objectKey'], size, sha)
        else:
            info = {'name': path.name, 'size': size, 'hash': md5, 'folderKey': self.folder}
            if size <= 8 * 1024 * 1024:
                def files_factory():
                    source = path.open('rb')
                    return {'metadataString': json.dumps(info)}, source, {'file': (path.name, source, 'application/octet-stream')}
                status, metadata = self.request('POST', self.upload_api + '/upload/files', files_factory=files_factory)
            else:
                status, metadata = self.request('POST', self.upload_api + '/upload/files/chunked/initiate', json_body=info)
                with path.open('rb') as source:
                    while status != 201:
                        offset, transaction = metadata.get('offset'), metadata.get('transactionId')
                        if not isinstance(offset, int) or not 0 <= offset < size or not isinstance(transaction, str) or not transaction:
                            raise UploadError('Jio returned an invalid chunk continuation.')
                        source.seek(offset)
                        chunk = source.read(min(CHUNK, size - offset))
                        previous = offset
                        status, metadata = self.request('PUT', self.upload_api + '/upload/files/chunked?' + urlencode({'uploadId': transaction}),
                                                        raw=chunk, extra={'X-Offset': str(offset),
                                                        'Content-MD5': hashlib.md5(chunk).hexdigest(),
                                                        'Content-Type': 'application/octet-stream', 'processData': 'false'})
                        if status != 201 and metadata.get('offset', -1) <= previous:
                            raise UploadError('Jio chunk upload did not advance.')
            if status != 201 or not isinstance(metadata.get('objectKey'), str):
                raise UploadError('Jio did not confirm the completed file upload.')
            if metadata.get('parentObjectKey') != self.folder or metadata.get('objectName') != path.name:
                raise UploadError('Jio returned an unexpected stored-file destination.')
            self.remote[path.name] = [metadata]
            receipt = {'objectKey': metadata['objectKey'], 'bytes': size, 'sha256': sha, 'md5': md5, 'verified': False}
            self.checkpoint(path.name, receipt)
            self.verify(metadata['objectKey'], size, sha)
        receipt = {'objectKey': metadata['objectKey'], 'bytes': size, 'sha256': sha, 'md5': md5, 'verified': True}
        self.checkpoint(path.name, receipt)
        return receipt

    def run(self, test_only=False, ready_only=False):
        prepared = json.loads((self.directory / 'prepared-models.json').read_text(encoding='utf-8'))
        entries = sorted(prepared.items(), key=lambda pair: pair[1]['bytes'])
        if ready_only:entries=[pair for pair in entries if pair[1].get('preview')]
        if test_only:
            # Exercise chunked transfer as well as the already verified small file.
            entries = [next(pair for pair in entries if pair[1]['bytes'] > 8 * 1024 * 1024)]
        failed = []
        errors = {}
        def upload_asset(path,expected_sha=None):
            # Changed source files get immutable object names. Keep the logical
            # ID stable without overwriting packages older installs may use.
            old=self.assets.get(path.name,{})
            remote_name=old.get('remoteName') or path.name
            remote=self.remote.get(remote_name,[])
            known_sha=expected_sha or (digest_file(path) if path.is_file() else old.get('sha256'))
            if old.get('verified') and old.get('sha256')==known_sha and any(
                item.get('objectKey')==old.get('objectKey') and int(item.get('sizeInBytes',item.get('size',0)))==old.get('bytes')
                and (not item.get('hash') or item['hash'].lower()==old.get('md5','').lower()) for item in remote):return old
            if not path.is_file():
                # Cloud-verified staging copies may have been deliberately cleaned
                # up. Reuse only this account's checked object, with matching size
                # and content receipt; never fabricate a fresh upload/checksum.
                raise UploadError('A staging asset is missing and its cloud receipt could not be confirmed. Restore/reprepare this package before retrying.')
            sha=expected_sha or digest_file(path)
            remote_name=old.get('remoteName') if old.get('sha256')==sha else None
            if old and old.get('sha256')!=sha:
                remote_name=path.stem+'-'+sha[:16]+path.suffix
            if remote_name:
                versioned=path.with_name(remote_name)
                if not versioned.is_file() or digest_file(versioned)!=sha:
                    import shutil
                    shutil.copyfile(path,versioned)
                receipt=self.upload_file(versioned,sha)
                receipt={**receipt,'remoteName':remote_name}
                self.checkpoint(path.name,receipt)
                return receipt
            return self.upload_file(path,sha)
        def upload_entry(pair):
            identifier, entry = pair
            for attempt in range(4):
                try:
                    package = upload_asset(self.directory / (identifier + '.zip'), entry['sha256'])
                    preview = upload_asset(self.directory / (identifier + '.webp')) if entry.get('preview') else None
                    return identifier, package, preview
                except (requests.RequestException, UploadError, ConnectionError) as exc:
                    if attempt == 3:
                        raise
                    detail = str(exc) if isinstance(exc, (UploadError, ConnectionError)) else type(exc).__name__
                    print(f'Retrying {identifier}: {detail}', flush=True)
                    time.sleep(2 ** attempt)
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            jobs = {pool.submit(upload_entry, entry): entry[0] for entry in entries}
            completed = 0
            for job in as_completed(jobs):
                try:
                    identifier, package, preview = job.result()
                    completed += 1
                    print(f'Verified packages: {completed}/{len(entries)} · {identifier}', flush=True)
                except Exception as exc:
                    identifier = jobs[job]
                    failed.append(identifier)
                    errors[identifier] = str(exc) if isinstance(exc, (UploadError, ConnectionError)) else type(exc).__name__
                    # Do not print arbitrary requests errors: URLs may contain upload IDs.
                    print(f'Deferred {identifier}: {errors[identifier]}', flush=True)
        summary = {'total': len(entries), 'completed': completed, 'failed': failed, 'errors': errors,
                   'verifiedAssets': sum(bool(x.get('verified')) for x in self.assets.values()), 'testOnly': test_only}
        (self.directory / 'jio-upload-report.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        if not failed and not test_only:
            catalogue=self.directory/'catalogue.json'
            existing=self.assets.get(catalogue.name)
            if existing and existing.get('sha256')!=digest_file(catalogue):
                versioned=self.directory/('catalogue-'+digest_file(catalogue)[:16]+'.json')
                versioned.write_bytes(catalogue.read_bytes())
                catalogue=versioned
            self.upload_file(catalogue)
        print(json.dumps(summary), flush=True)
        return 2 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parents[2] / 'private-model-library')
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=3)
    parser.add_argument('--test-only', action='store_true')
    parser.add_argument('--ready-only',action='store_true',help='Transfer only packages with completed rotating previews.')
    parser.add_argument('--remote-folder',choices=['PMX/Sakura library packages'])
    args = parser.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.platform == 'win32':
        import msvcrt
        upload_lock = (args.directory / 'jio-upload.lock').open('a+b')
        upload_lock.seek(0)
        upload_lock.write(b'1')
        upload_lock.flush()
        upload_lock.seek(0)
        try:
            msvcrt.locking(upload_lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise UploadError('A Jio upload pass is already running.') from None
    return JioUploader(args.directory, workers=args.workers,remote_folder=args.remote_folder).run(test_only=args.test_only,ready_only=args.ready_only)


if __name__ == '__main__':
    raise SystemExit(main())
