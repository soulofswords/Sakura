"""Owner connector security and destination checks; no real account or OTP."""
import base64
import hashlib
import hmac
import importlib.util
import json
import threading
from pathlib import Path

import pytest
import requests


SPEC = importlib.util.spec_from_file_location('jio_library_owner', Path(__file__).parents[1] / 'tools/jio_library_owner.py')
jio = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(jio)


class Store:
    def __init__(self):
        self.value = None

    def save(self, value):
        self.value = json.loads(json.dumps(value))

    def load(self):
        return self.value or {}


class Response:
    def __init__(self, value, status=200):
        self.value, self.status_code = value, status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, size):
        yield json.dumps(self.value).encode()


class Transport:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        result = self.replies.pop(0)
        return result if isinstance(result, Response) else Response(result)


def connection(replies=()):
    transport = Transport(replies)
    owner = jio.JioConnection(store=Store(), transport=transport)
    owner.headers = {'X-Api-Key': 'public-web-key'}
    return owner, transport


def session(**kwargs):
    return {'userId': 'owner-123', 'deviceKey': 'device-123', 'rootFolderKey': 'root', 'dcGroupCode': 'JMNG2',
            'authToken': {'accessToken': 'secret-access-token', 'refreshToken': 'secret-refresh-token'}, **kwargs}


def test_rejected_login_can_restart_without_deleting_saved_recovery():
    owner, transport=connection()
    owner.session=session(twoFAValidated=True)
    owner.store.save({'session':owner.session})
    saved=owner.store.load()
    owner.profile={'userId':'owner-123'}
    owner.candidates=[{'id':'folder'}]
    owner.destination={'folderKey':'folder'}
    owner.last_error={'status':401}
    owner.reset_login()
    assert not owner.public()['otpAccepted']
    assert not owner.public()['canInspect']
    assert not owner.public()['connected']
    assert owner.store.load()==saved


def profile():
    return {'userId': 'owner-123', 'emailId': 'owner@example.com', 'rootFolderKey': 'root', 'dcGroupCode': 'JMNG2'}


def folder(key='folder-123', name='live2d'):
    return {'objectKey': key, 'objectName': name}


def test_otp_login_does_not_save_until_owner_confirms_folder():
    owner, transport = connection([{}, session(), profile(), {'objects': [folder()]}])
    owner.send_otp('owner@example.com')
    owner.login('123456')
    assert owner.store.value['destination'] is None
    assert owner.public()['folder'] == 'live2d'
    assert not owner.public()['connected']
    owner.confirm()
    assert owner.store.value['destination']['folderKey'] == 'folder-123'
    assert owner.store.value['destination']['userId'] == 'owner-123'
    assert owner.public()['connected']
    assert all(not ('upload' in url or 'share' in url) for _, url, _ in transport.calls)
    assert 'type=w' in transport.calls[-1][1]
    assert transport.calls[-1][1].startswith('https://jmng2-api.jioaicloud.com/')
    assert all(not kwargs['allow_redirects'] for _, _, kwargs in transport.calls)
    assert 'secret-access-token' not in json.dumps(owner.public())
    assert 'secret-refresh-token' not in json.dumps(owner.public())


@pytest.mark.parametrize('objects', [[], [folder('a'), folder('b')]])
def test_missing_or_duplicate_destination_does_not_save(objects):
    owner, _ = connection([profile(), {'objects': objects}])
    owner.session = session(twoFAValidated=True)
    owner.inspect()
    with pytest.raises(jio.ConnectionError):
        owner.confirm()
    assert owner.store.value['destination'] is None


def test_account_identity_mismatch_blocks_folder_access_and_save():
    owner, transport = connection([{'userId': 'somebody-else'}])
    owner.session = session(twoFAValidated=True)
    with pytest.raises(jio.ConnectionError, match='identity'):
        owner.inspect()
    with pytest.raises(jio.ConnectionError):
        owner.confirm()
    assert len(transport.calls) == 1
    assert owner.store.value is None


@pytest.mark.parametrize('next_link', ['https://attacker.example/nms/metadata/next',
                                     'https://jaws-api.jioaicloud.com/nms/metadata/next',
                                     '//attacker.example/nms/metadata/next'])
def test_pagination_cannot_exfiltrate_tokens(next_link):
    owner, transport = connection([profile(), {'objects': [], 'nextLink': next_link}])
    owner.session = session(twoFAValidated=True)
    with pytest.raises(jio.ConnectionError):
        owner.inspect()
    assert len(transport.calls) == 2


def test_destination_found_on_second_page_and_repeated_page_rejected():
    owner, _ = connection([profile(), {'objects': [], 'nextLink': '/nms/metadata/next'}, {'objects': [folder(name='Live2D')]}])
    owner.session = session(twoFAValidated=True)
    owner.inspect()
    assert owner.public()['folder'] == 'Live2D'
    owner, _ = connection([profile(), {'objects': [], 'nextLink': '/nms/metadata/repeat'},
                           {'objects': [], 'nextLink': '/nms/metadata/repeat'}])
    owner.session = session(twoFAValidated=True)
    with pytest.raises(jio.ConnectionError, match='repeated'):
        owner.inspect()


@pytest.mark.parametrize('region', ['UNRECOGNIZED', 'https://attacker.example'])
def test_unrecognized_region_fails_closed(region):
    owner, transport = connection([{**profile(), 'dcGroupCode': region}])
    owner.session = session(twoFAValidated=True)
    with pytest.raises(jio.ConnectionError, match='region'):
        owner.inspect()
    assert len(transport.calls) == 1


def test_two_factor_session_never_becomes_connected_before_unlock():
    owner, transport = connection([{}, session(isTwoFAEnabled='Y', encTwoFASessionKey='challenge')])
    owner.send_otp('9876543210')
    owner.login('123456')
    assert owner.public()['needsPassphrase']
    assert owner.store.value is None
    assert len(transport.calls) == 2
    with pytest.raises(jio.ConnectionError):
        owner.confirm()


def test_email_otp_uses_browser_metadata_from_the_official_web_contract():
    owner, transport = connection([{}, session(), profile(), {'objects': [folder()]}])
    owner.send_otp('owner@example.com')
    owner.login('123456', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/142.0.7444.60 Safari/537.36')
    payload = transport.calls[1][2]['json']
    assert payload['emailId'] == 'owner@example.com'
    assert payload['deviceInfo']['platformType'] == 'Chrome'
    assert payload['deviceInfo']['platformVersion'] == '142.0.7444.60'


def test_folder_error_preserves_accepted_otp_and_retries_without_another_login():
    owner, transport = connection([{}, session(), profile(), Response({'code': 'TEJRF0400', 'error': 'sensitive provider prose'}, 400),
                                   profile(), {'objects': [folder()]}])
    owner.send_otp('owner@example.com')
    with pytest.raises(jio.ConnectionError, match='finding the live2d folder.*TEJRF0400') as caught:
        owner.login('123456')
    assert 'sensitive provider prose' not in str(caught.value)
    assert owner.public()['otpAccepted']
    assert owner.public()['canInspect']
    assert not owner.public()['otpRequested']
    assert owner.public()['lastError'] == {'stage': 'finding the live2d folder', 'status': 400, 'code': 'TEJRF0400'}
    owner.login('123456')
    assert owner.public()['folderCount'] == 1
    assert sum('/account/otp/login' in url for _, url, _ in transport.calls) == 1


def test_folder_query_matches_official_picker_and_verified_session_survives_restart():
    owner, transport = connection([{}, session(), profile(), Response({'code': 'NMSOM0001'}, 400)])
    owner.send_otp('owner@example.com')
    with pytest.raises(jio.ConnectionError):
        owner.login('123456')
    from urllib.parse import urlsplit, parse_qs
    query = parse_qs(urlsplit(transport.calls[-1][1]).query)
    assert urlsplit(transport.calls[-1][1]).path == '/nms/metadata'
    assert query == {'limit': ['2000'], 'folderKey': ['root'], 'sort': ['+objectName'], 'type': ['w']}
    assert owner.store.value['session']['twoFAValidated']
    assert owner.store.value['destination'] is None
    resumed, resumed_transport = connection([profile(), {'objects': [folder(name='Live2d')]}])
    resumed.store = owner.store
    resumed.resume()
    assert resumed.public()['folder'] == 'Live2d'
    assert not resumed.public()['connected']
    assert not any('/account/otp/login' in url for _, url, _ in resumed_transport.calls)


def test_nms_requests_include_the_required_accept_language_header():
    owner, transport = connection([{'envHeaders': {'X-Api-Key': 'public-key', 'X-App-Secret': 'public-app-secret'}},
                                   profile(), {'objects': [folder()]}])
    owner.headers = None
    owner.session = session(twoFAValidated=True)
    owner.configure()
    owner.inspect()
    assert all(call[2]['headers']['Accept-Language'] == 'en' for call in transport.calls[1:])


def test_saved_destination_survives_resume_only_if_account_and_folder_still_match():
    owner, _ = connection([profile(), {'objects': [folder()]}])
    owner.store.value = {'session': session(twoFAValidated=True), 'destination': {
        'userId': 'owner-123', 'folderKey': 'folder-123', 'name': 'live2d'}}
    owner.resume()
    assert owner.public()['connected']
    assert owner.store.value['destination']['folderKey'] == 'folder-123'
    owner, _ = connection([profile(), {'objects': [folder('different-folder')]}])
    owner.store.value = {'session': session(twoFAValidated=True), 'destination': {
        'userId': 'owner-123', 'folderKey': 'folder-123', 'name': 'live2d'}}
    owner.resume()
    assert not owner.public()['connected']
    assert owner.store.value['destination'] is None


def test_expired_saved_session_refresh_uses_official_put_payload():
    owner, transport=connection([Response({'code':'TEJGA0401'},401),{'accessToken':'new-token','refreshToken':'new-refresh'},
                                 profile(),{'objects':[folder()]}])
    owner.store.value={'session':session(twoFAValidated=True),'destination':{'userId':'owner-123','folderKey':'folder-123'}}
    owner.resume()
    method,url,options=transport.calls[1]
    assert method=='PUT'
    assert url.endswith('/account/token/refresh')
    assert options['json']['jToken'] is True
    assert options['json']['isIdamOn']=='true'
    assert options['json']['deviceInfo']['deviceKey']=='device-123'
    assert owner.session['authToken']['accessToken']=='new-token'
    assert owner.public()['connected']


def test_incorrect_otp_is_bounded_and_errors_do_not_expose_provider_secrets():
    owner, transport = connection([{}, *[Response({'secret': 'never-display-this'}, 401) for _ in range(5)]])
    owner.send_otp('9876543210')
    for _ in range(5):
        with pytest.raises(jio.ConnectionError) as caught:
            owner.login('000000')
        assert 'never-display-this' not in str(caught.value)
    with pytest.raises(jio.ConnectionError, match='new OTP'):
        owner.login('000000')
    with pytest.raises(jio.ConnectionError, match='60 seconds'):
        owner.send_otp('9876543210')
    assert len(transport.calls) == 6


def test_two_factor_proof_matches_protocol_roundtrip():
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7
    user, password, session_key = 'owner-123', 'test passphrase', 'provider-session-key'
    hashed = hmac.new(user.encode(), password.encode(), hashlib.sha256).hexdigest()

    def cipher(key):
        return Cipher(algorithms.AES(hashlib.sha1(key.encode()).digest()[:16]), modes.ECB())

    padder = PKCS7(128).padder()
    plain = padder.update(('owner#' + session_key).encode()) + padder.finalize()
    enc = cipher(hashed).encryptor()
    challenge = base64.b64encode(enc.update(plain) + enc.finalize()).decode()
    proof = jio.two_fa_header(user, password, challenge, now=12345)
    dec = cipher(session_key).decryptor()
    padded = dec.update(base64.b64decode(proof)) + dec.finalize()
    unpadder = PKCS7(128).unpadder()
    assert (unpadder.update(padded) + unpadder.finalize()).decode() == f'{user}#{hashed}#12345000'
    with pytest.raises(jio.ConnectionError):
        jio.two_fa_header(user, 'wrong password', challenge)


def test_local_server_blocks_cross_origin_missing_capability_and_wrong_host():
    owner, transport = connection()
    server, url = jio.make_server(owner, token='test-capability')
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = url.split('#')[0].rstrip('/')
    try:
        headers = {'X-Sakura-Owner': 'test-capability'}
        assert requests.get(base + '/').status_code == 200
        assert requests.post(base + '/api/status', json={}).status_code == 403
        assert requests.post(base + '/api/status', json={}, headers={**headers, 'Origin': 'https://attacker.example'}).status_code == 403
        assert requests.post(base + '/api/status', json={}, headers={**headers, 'Host': 'attacker.example'}).status_code == 403
        reply = requests.post(base + '/api/status', json={}, headers=headers)
        assert reply.status_code == 200
        assert reply.headers['Cache-Control'] == 'no-store'
        assert requests.post(base + '/api/upload', json={}, headers=headers).status_code == 404
        assert requests.post(base + '/api/status', json=[], headers=headers).status_code == 400
        assert not transport.calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_profile_401_returns_a_fresh_login_state():
    owner, transport=connection([Response({'code':'TEJGA0401'},401)])
    owner.session=session(twoFAValidated=True)
    server,url=jio.make_server(owner,token='test-capability')
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        response=requests.post(url.split('#')[0].rstrip('/')+'/api/inspect',json={},headers={'X-Sakura-Owner':'test-capability'})
        assert response.status_code==400
        assert 'TEJGA0401' in response.json()['error']
        assert response.json()['state']['otpAccepted'] is False
        assert response.json()['state']['canInspect'] is False
        assert owner.session=={}
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)


@pytest.mark.skipif(__import__('sys').platform != 'win32', reason='Windows DPAPI')
def test_dpapi_storage_is_encrypted_and_roundtrips(tmp_path):
    store = jio.EncryptedState(tmp_path / '.owner.bin')
    value = {'session': session(), 'destination': {'name': 'live2d'}}
    store.save(value)
    assert b'secret-access-token' not in store.path.read_bytes()
    assert b'secret-refresh-token' not in store.path.read_bytes()
    assert store.load() == value
