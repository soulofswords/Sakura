"""Transfer invariants with local bytes and simulated provider replies."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import threading

import pytest

TOOLS = Path(__file__).parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location('jio_upload', TOOLS / 'upload-library-jio.py')
upload = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upload)


def uploader(tmp_path):
    value = upload.JioUploader.__new__(upload.JioUploader)
    value.folder = 'confirmed-folder'
    value.user_id = 'owner'
    value.directory = tmp_path
    value.ledger_path = tmp_path / 'ledger.json'
    value.ledger_lock = threading.RLock()
    value.remote = {}
    value.assets = {}
    value.upload_api = 'https://jaws-upload.jioaicloud.com'
    value.download_api = 'https://jaws-dl.jioaicloud.com'
    value.allowed_hosts = {'jaws-upload.jioaicloud.com', 'jaws-dl.jioaicloud.com'}
    return value


def test_cleaned_staging_copy_reuses_confirmed_remote_asset(tmp_path,monkeypatch):
    owner=uploader(tmp_path);owner.workers=1
    entry={'id':'model','bytes':10,'sha256':'a'*64,'preview':False}
    (tmp_path/'prepared-models.json').write_text(json.dumps({'model':entry}))
    (tmp_path/'catalogue.json').write_text('{}')
    receipt={'objectKey':'remote','bytes':10,'sha256':'a'*64,'md5':'b'*32,'verified':True}
    owner.assets={'model.zip':receipt};owner.remote={'model.zip':[{'objectKey':'remote','sizeInBytes':10,'hash':'b'*32}]}
    calls=[];owner.upload_file=lambda path,*args:calls.append(path.name)
    assert owner.run()==0
    assert calls==['catalogue.json']
    # Immutable remote names use the logical receipt even if a local copy exists.
    (tmp_path/'model.zip').write_bytes(b'local staging bytes are not needed with a validated expected SHA')
    receipt['remoteName']='model-version.zip';owner.remote={'model-version.zip':owner.remote['model.zip']}
    assert owner.run()==0
    assert calls==['catalogue.json','catalogue.json']
    (tmp_path/'model.zip').unlink()
    owner.remote={}
    monkeypatch.setattr(upload.time,'sleep',lambda value:None)
    assert owner.run()==2


def test_small_upload_uses_confirmed_folder_and_requires_full_download_verification(tmp_path):
    owner = uploader(tmp_path)
    path = tmp_path / 'model.zip'
    path.write_bytes(b'prepared model package')
    calls, checked = [], []

    def request(method, url, **kwargs):
        calls.append((method, url))
        form, opened, files = kwargs['files_factory']()
        try:
            assert json.loads(form['metadataString']) == {
                'name': path.name, 'size': path.stat().st_size, 'folderKey': 'confirmed-folder',
                'hash': hashlib.md5(path.read_bytes()).hexdigest()}
            assert files['file'][1].read() == path.read_bytes()
        finally:
            opened.close()
        return 201, {'objectKey': 'remote-file', 'parentObjectKey': 'confirmed-folder', 'objectName': path.name}

    owner.request = request
    owner.verify = lambda *args: checked.append(args)
    receipt = owner.upload_file(path)
    assert receipt['verified']
    assert checked == [('remote-file', path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())]
    assert len(calls) == 1
    assert json.loads(owner.ledger_path.read_text())['assets'][path.name]['verified']


def test_chunk_upload_sends_offset_and_checksum_and_handles_resume(tmp_path):
    owner = uploader(tmp_path)
    path = tmp_path / 'large.zip'
    content = b'x' * (2 * upload.CHUNK + 1024 * 1024)
    path.write_bytes(content)
    offsets = []

    def request(method, url, **kwargs):
        if method == 'POST':
            return 200, {'offset': upload.CHUNK, 'transactionId': 'resume-id'}
        offset = int(kwargs['extra']['X-Offset'])
        chunk = kwargs['raw']
        offsets.append(offset)
        assert kwargs['extra']['Content-MD5'] == hashlib.md5(chunk).hexdigest()
        assert kwargs['extra']['Content-Type'] == 'application/octet-stream'
        assert chunk == content[offset:offset + len(chunk)]
        assert 'uploadId=resume-id' in url
        if offset + len(chunk) == len(content):
            return 201, {'objectKey': 'remote-large', 'parentObjectKey': 'confirmed-folder', 'objectName': path.name}
        return 200, {'offset': offset + len(chunk), 'transactionId': 'resume-id'}

    owner.request = request
    owner.verify = lambda *args: None
    assert owner.upload_file(path)['verified']
    assert offsets == [upload.CHUNK, 2 * upload.CHUNK]


def test_upload_never_accepts_an_unexpected_destination(tmp_path):
    owner = uploader(tmp_path)
    path = tmp_path / 'model.zip'
    path.write_bytes(b'package')
    owner.request = lambda *args, **kwargs: (201, {'objectKey': 'remote', 'parentObjectKey': 'other-folder', 'objectName': path.name})
    owner.verify = lambda *args: pytest.fail('Do not accept a mismatched destination')
    with pytest.raises(upload.UploadError, match='destination'):
        owner.upload_file(path)
    assert not owner.assets


def test_same_name_conflict_is_not_overwritten(tmp_path):
    owner = uploader(tmp_path)
    path = tmp_path / 'model.zip'
    path.write_bytes(b'new package')
    owner.remote[path.name] = [{'objectKey': 'existing', 'sizeInBytes': 1}]
    owner.request = lambda *args, **kwargs: pytest.fail('Must not overwrite an existing file')
    with pytest.raises(upload.UploadError, match='not overwritten'):
        owner.upload_file(path)


def test_existing_file_is_verified_and_reused_without_upload(tmp_path):
    owner = uploader(tmp_path)
    path = tmp_path / 'model.zip'
    path.write_bytes(b'package')
    owner.remote[path.name] = [{'objectKey': 'existing', 'sizeInBytes': path.stat().st_size}]
    owner.request = lambda *args, **kwargs: pytest.fail('Existing content must be read and verified')
    checked = []
    owner.verify = lambda *args: checked.append(args)
    assert owner.upload_file(path)['objectKey'] == 'existing'
    assert len(checked) == 1
    # A valid checkpoint can resume only if its remote object still exists.
    owner.verify = lambda *args: pytest.fail('A verified existing checkpoint is reusable')
    assert owner.upload_file(path)['verified']


def test_corrupted_local_package_is_rejected_before_network(tmp_path):
    owner = uploader(tmp_path)
    path = tmp_path / 'model.zip'
    path.write_bytes(b'changed')
    owner.request = lambda *args, **kwargs: pytest.fail('Invalid local bytes must never upload')
    with pytest.raises(upload.UploadError, match='catalogue'):
        owner.upload_file(path, expected_sha='0' * 64)


def test_download_must_match_size_and_sha256(tmp_path):
    owner = uploader(tmp_path)

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_content(self, size): yield b'wrong bytes'

    owner.request = lambda *args, **kwargs: Response()
    with pytest.raises(upload.UploadError, match='SHA256'):
        owner.verify('remote', len(b'wrong bytes'), '0' * 64)
    with pytest.raises(upload.UploadError, match='more bytes'):
        owner.verify('remote', 1, '0' * 64)


def test_external_service_cannot_receive_owner_credentials(tmp_path):
    owner = uploader(tmp_path)
    with pytest.raises(upload.UploadError, match='Unexpected Jio'):
        owner.request('POST', 'https://attacker.example/upload')


def test_changed_package_uses_immutable_name_and_resumes_same_version(tmp_path):
    owner=uploader(tmp_path);owner.workers=1
    identifier='pmx-example';package=tmp_path/(identifier+'.zip');package.write_bytes(b'new package')
    sha=hashlib.sha256(package.read_bytes()).hexdigest()
    owner.assets[package.name]={'sha256':'0'*64,'verified':True,'objectKey':'old-object'}
    (tmp_path/'prepared-models.json').write_text(json.dumps({identifier:{'bytes':package.stat().st_size,'sha256':sha,'preview':False}}))
    (tmp_path/'catalogue.json').write_text('{}')
    calls=[]
    def put(path,expected_sha=None):
        calls.append(path.name)
        assert expected_sha is None or hashlib.sha256(path.read_bytes()).hexdigest()==expected_sha
        return {'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'verified':True,'objectKey':'new-object'}
    owner.upload_file=put
    assert owner.run()==0
    versioned=identifier+'-'+sha[:16]+'.zip'
    assert calls[0]==versioned
    assert owner.assets[package.name]['remoteName']==versioned
    assert owner.assets[package.name]['objectKey']=='new-object'
    calls.clear();assert owner.run()==0
    assert calls[0]==versioned,'Retries must reuse the same immutable remote filename.'


def test_transfer_streams_bodies_instead_of_one_large_tls_write(tmp_path):
    from types import SimpleNamespace
    owner = uploader(tmp_path)
    owner.auth_lock = threading.RLock()
    owner.connection = SimpleNamespace(session={'authToken': {'accessToken': 'test-token'}})
    owner.headers = lambda: {'Content-Type': 'application/json', 'Accept-Language': 'en'}
    calls = []

    class Response:
        status_code = 201
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_content(self, size): yield b'{"objectKey":"uploaded"}'

    class HTTP:
        def request(self, method, url, **kwargs):
            body = kwargs['data']
            assert hasattr(body, 'read')
            calls.append((kwargs['headers'], body.read()))
            return Response()

    owner.http = lambda: HTTP()
    owner.request('PUT', owner.upload_api + '/upload/files/chunked?uploadId=test',
                  raw=b'chunk bytes', extra={'Content-Type': 'application/octet-stream'})
    path = tmp_path / 'small.zip'
    path.write_bytes(b'package')

    def factory():
        opened = path.open('rb')
        return {'metadataString': '{"folderKey":"confirmed"}'}, opened, {'file': (path.name, opened)}

    owner.request('POST', owner.upload_api + '/upload/files', files_factory=factory)
    assert calls[0][1] == b'chunk bytes'
    assert calls[1][0]['Content-Type'].startswith('multipart/form-data; boundary=')
    assert b'package' in calls[1][1]
    assert b'confirmed' in calls[1][1]


def test_ready_batch_never_uploads_a_model_without_its_preview(tmp_path):
    owner=uploader(tmp_path);owner.workers=1;seen=[]
    (tmp_path/'ready.zip').write_bytes(b'package');(tmp_path/'ready.webp').write_bytes(b'preview')
    (tmp_path/'prepared-models.json').write_text(json.dumps({'ready':{'bytes':1,'sha256':'a'*64,'preview':True},'pending':{'bytes':2,'sha256':'b'*64,'preview':False}}))
    owner.upload_file=lambda path,sha=None:(seen.append(path.name) or {'verified':True,'sha256':sha or 'c'*64})
    result=owner.run(ready_only=True)
    assert result==0
    assert seen==['ready.zip','ready.webp','catalogue.json']
