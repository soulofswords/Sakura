"""Read-only recursive Jio/local folder comparison by path, size and MD5."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
from urllib.parse import urlencode, quote

import requests
from jio_library_owner import JioConnection, REGIONS, ConnectionError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local', type=Path, required=True)
    parser.add_argument('--remote', required=True, help='Folder path from My Files, separated by /')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    owner = JioConnection()
    owner.resume()
    if not owner.session.get('twoFAValidated'):raise ValueError('Reconnect the owner Jio account before auditing.')
    region = REGIONS[owner.session['dcGroupCode']]
    origin = f'https://{region}-api.jioaicloud.com'
    local_threads = threading.local()

    def client():
        if not hasattr(local_threads, 'client'):
            c = JioConnection(store=owner.store)
            c.headers = owner.headers
            c.session = owner.session
            local_threads.client = c
        return local_threads.client

    def listing(key):
        url = origin + '/nms/metadata?' + urlencode({'limit': 2000, 'folderKey': key, 'sort': '+objectName'})
        result, seen = [], set()
        for _ in range(100):
            if url in seen or not (url.startswith(origin + '/nms/metadata?') or url.startswith(origin + '/nms/metadata/')):
                raise ValueError('Invalid provider pagination.')
            seen.add(url)
            for attempt in range(4):
                try:
                    page = client().request('GET', url, authenticated=True)
                    break
                except (ConnectionError, requests.RequestException):
                    if attempt == 3:
                        raise
                    time.sleep(2 ** attempt)
            if not isinstance(page.get('objects'), list):
                raise ValueError('Invalid provider folder list.')
            result.extend(page['objects'])
            link = page.get('nextLink')
            if not link:
                return result
            url = origin + link if isinstance(link, str) and link.startswith('/') and not link.startswith('//') else link
        raise ValueError('Too many pages.')

    key = owner.session['rootFolderKey']
    for component in args.remote.strip('/').split('/'):
        found = [entry for entry in listing(key) if entry.get('objectType') == 'FR'
                 and str(entry.get('objectName', '')).casefold() == component.casefold()]
        if len(found) != 1:
            raise ValueError('Remote folder is missing or ambiguous: ' + component)
        key = found[0]['objectKey']
    remote, directories, duplicates = {}, [], []
    jobs = [(key, '')]
    seen_keys = set()
    with ThreadPoolExecutor(max_workers=4) as pool:
        while jobs:
            futures = {pool.submit(listing, identifier): (identifier, prefix) for identifier, prefix in jobs}
            jobs = []
            for future in as_completed(futures):
                identifier, prefix = futures[future]
                if identifier in seen_keys:
                    raise ValueError('Remote folder cycle detected.')
                seen_keys.add(identifier)
                for item in future.result():
                    name = item.get('objectName', '')
                    if not isinstance(name, str) or not name or '/' in name or '\\' in name or name in ('.', '..'):
                        raise ValueError('Unsupported remote file name.')
                    path = prefix + name
                    if item.get('objectType') == 'FR':
                        directories.append(path)
                        jobs.append((item['objectKey'], path + '/'))
                    else:
                        if path in remote:
                            duplicates.append(path)
                        remote[path] = item
            print(f'Listed {len(seen_keys)} folders, {len(remote)} files; {len(jobs)} folders remain.', flush=True)
    local = {p.relative_to(args.local).as_posix(): p for p in args.local.rglob('*') if p.is_file()}
    missing = sorted(set(local) - set(remote))
    extra = sorted(set(remote) - set(local))
    mismatch, hash_mismatch, hash_checked = [], [], 0

    def compare(path):
        item, source = remote[path], local[path]
        size = source.stat().st_size
        if size != int(item.get('sizeInBytes', -1)):
            return 'size', {'path': path, 'localBytes': size, 'remoteBytes': item.get('sizeInBytes')}
        digest = item.get('hash')
        if not digest:
            detail = client().request('GET', origin + '/nms/metadata/' + quote(item['objectKey'], safe='') + '/info', authenticated=True)
            digest = detail.get('hash')
        if not digest:
            return 'unavailable', path
        with source.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'md5').hexdigest()
        return ('match' if actual.lower() == str(digest).lower() else 'hash'), path

    unavailable = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks = [pool.submit(compare, path) for path in sorted(set(local) & set(remote))]
        for future in as_completed(tasks):
            kind, value = future.result()
            if kind == 'size': mismatch.append(value)
            elif kind == 'hash': hash_mismatch.append(value)
            elif kind == 'unavailable': unavailable.append(value)
            else: hash_checked += 1
    report = {'remotePath': args.remote, 'localPath': str(args.local), 'localFiles': len(local),
              'remoteFiles': len(remote), 'remoteFolders': len(directories), 'missing': missing,
              'extra': extra, 'sizeMismatches': mismatch, 'hashMismatches': hash_mismatch,
              'hashesMatched': hash_checked, 'hashUnavailable': unavailable, 'duplicatePaths': duplicates,
              'missingFileDetails': [{'path': path, 'bytes': local[path].stat().st_size} for path in missing]}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
