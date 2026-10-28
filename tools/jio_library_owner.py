"""Owner-only JioAICloud login and destination check. No upload operations.

Run with the owner's Python: python tools/jio_library_owner.py
This utility is not a tester feature and does not read Chrome's saved sessions.
"""
import argparse
import os
import base64
import hashlib
import hmac
import json
import re
import secrets
import sys
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import requests

SECURITY = 'https://api.jioaicloud.com'
PUBLIC_CONFIG = 'https://www.jioaicloud.com/assets/runtime-config.json'
REGIONS = {'JAWS': 'jaws', 'JMNG': 'jmng1', 'JMNG2': 'jmng2'}
def account_id():
    value=os.environ.get('SAKURA_JIO_ACCOUNT','primary')
    if value not in ('primary','account2'):raise ValueError('Unknown owner storage account.')
    return value

def private_directory(kind='live2d',root=None):
    suffix='-pmx' if kind=='pmx' else ''
    account='' if account_id()=='primary' else '-'+account_id()
    return (Path(root).parent if root is not None else Path(__file__).resolve().parents[2])/('private-model-library'+account+suffix)

DEFAULT_STATE = private_directory() / '.jio-owner-session.bin' 


class ConnectionError(ValueError):
    """A deliberately sanitized error suitable for the local owner page."""


def login_identity(value):
    value = str(value).strip()
    if re.fullmatch(r'[^\s@]{1,100}@[^\s@]{1,140}\.[^\s@]{2,30}', value):
        return {'emailId': value, 'mobileNumber': ''}
    digits = re.sub(r'[\s()+-]', '', value)
    if len(digits) == 10:
        digits = '91' + digits
    if not re.fullmatch(r'91\d{10}', digits):
        raise ConnectionError('Enter your JioAICloud email or Indian mobile number.')
    return {'emailId': '', 'mobileNumber': '+' + digits}


def mask_identity(value):
    value = str(value or '')
    if '@' in value:
        name, domain = value.split('@', 1)
        return name[:2] + '***@' + domain
    return ('***' + value[-4:]) if value else 'Not supplied by Jio'


def browser_details(user_agent):
    # Jio's own OTP screen sends deviceService.browser/browser_version here,
    # not the OS name/version. Keep the same contract as that screen.
    for pattern, name in ((r'Edg/([\d.]+)', 'MS-Edge-Chromium'),
                          (r'Firefox/([\d.]+)', 'Firefox'),
                          (r'Chrome/([\d.]+)', 'Chrome')):
        found = re.search(pattern, str(user_agent)[:1000])
        if found:
            return name, found.group(1)[:40]
    return 'Chrome', '130.0.0.0'


def request_stage(url):
    path = urlsplit(url).path
    if path.endswith('/otp/send'):
        return 'sending the OTP'
    if path.endswith('/otp/login'):
        return 'verifying the OTP'
    if path == '/security/users':
        return 'checking the account profile'
    if path.startswith('/nms/metadata'):
        return 'reading the Jio folders'
    if path == '/2fa/validation':
        return 'unlocking the passphrase'
    return 'loading the Jio connection'


def two_fa_header(user_id, passphrase, encrypted_key, now=None):
    # Jio's web protocol: HMAC-SHA256(passphrase, key=userId), AES-ECB/PKCS7.
    # These legacy algorithms are required by Jio; local persistence uses DPAPI.
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7
    hashed = hmac.new(user_id.encode(), passphrase.encode(), hashlib.sha256).hexdigest()

    def cipher(key):
        return Cipher(algorithms.AES(hashlib.sha1(key.encode()).digest()[:16]), modes.ECB())

    try:
        decryptor = cipher(hashed).decryptor()
        padded = decryptor.update(base64.b64decode(encrypted_key, validate=True)) + decryptor.finalize()
        unpadder = PKCS7(128).unpadder()
        plain = (unpadder.update(padded) + unpadder.finalize()).decode('utf-8')
        pieces = plain.split('#')
        if len(pieces) < 2 or not pieces[1]:
            raise ValueError()
        payload = f'{user_id}#{hashed}#{int((time.time() if now is None else now)*1000)}'.encode()
        padder = PKCS7(128).padder()
        padded = padder.update(payload) + padder.finalize()
        encryptor = cipher(pieces[1]).encryptor()
        return base64.b64encode(encryptor.update(padded) + encryptor.finalize()).decode()
    except (ValueError, UnicodeError, TypeError):
        raise ConnectionError('The Jio passphrase could not unlock this session.') from None


class EncryptedState:
    def __init__(self, path=None):
        self.path = Path(path or (private_directory()/'.jio-owner-session.bin'))

    @staticmethod
    def crypt(data, decrypt=False):
        if sys.platform != 'win32':
            raise ConnectionError('Owner session storage requires Windows DPAPI on this PC.')
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from credentials import _crypt
        return _crypt(data, decrypt=decrypt)

    def load(self):
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.crypt(self.path.read_bytes(), decrypt=True))
        except Exception:
            raise ConnectionError('Windows could not unlock the saved Jio connection. Reconnect on the owner PC.') from None

    def save(self, value):
        encrypted = self.crypt(json.dumps(value).encode())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_bytes(encrypted)
        temp.replace(self.path)


class JioConnection:
    def __init__(self, store=None, transport=None, folder_name=None):
        self.folder_name=folder_name or 'live2d'
        self.explicit_folder=folder_name is not None
        self.store = store or EncryptedState()
        self.http = transport or requests.Session()
        self.headers = None
        self.session = {}
        self.identity = None
        self.profile = {}
        self.candidates = []
        self.destination = None
        self.last_otp = 0
        self.attempts = 0
        self.last_error = {}
        self.message = 'Enter the account that owns your '+self.folder_name+' folder.'

    def request(self, method, url, body=None, authenticated=False, extra=None):
        # Retry only idempotent reads. OTP/login and other writes are never replayed.
        for attempt in range(3):
            try:
                return self._request_once(method,url,body,authenticated,extra)
            except ConnectionError as exc:
                if method.upper()!='GET' or getattr(exc,'status',None) not in (429,500,502,503,504) or attempt==2:raise
                time.sleep(2**attempt)

    def _request_once(self, method, url, body=None, authenticated=False, extra=None):
        # Never follow provider nextLink/redirects to a host carrying owner tokens.
        parsed = urlsplit(url)
        allowed = {'api.jioaicloud.com', 'www.jioaicloud.com'} | {
            f'{region}-api.jioaicloud.com' for region in REGIONS.values()}
        if (parsed.scheme != 'https' or parsed.hostname not in allowed or parsed.port not in (None, 443)
                or parsed.username or parsed.password or parsed.fragment):
            raise ConnectionError('Jio returned an unexpected service address. No credential was sent.')
        headers = dict(self.headers or {})
        if authenticated:
            token = self.session.get('authToken', {}).get('accessToken')
            if not token or not self.session.get('userId') or not self.session.get('deviceKey'):
                raise ConnectionError('Connect to JioAICloud first.')
            headers.update({'Authorization': 'Basic ' + base64.b64encode(token.encode()).decode(),
                            'X-User-Id': self.session['userId'], 'X-Device-Key': self.session['deviceKey']})
        headers.update(extra or {})
        try:
            with self.http.request(method, url, json=body, headers=headers, timeout=(10, 30),
                                   allow_redirects=False, stream=True) as response:
                parts = []
                size = 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 2_000_000:
                        raise ConnectionError('Jio returned an unexpectedly large connection response.')
                    parts.append(chunk)
                raw = b''.join(parts)
                try:
                    data = json.loads(raw) if raw.strip() else {}
                except ValueError:
                    data = {}
                if not 200 <= response.status_code < 300:
                    code = data.get('code', '') if isinstance(data, dict) else ''
                    code = code if isinstance(code, str) and re.fullmatch(r'[A-Z0-9_-]{1,40}', code) else ''
                    self.last_error = {'stage': request_stage(url), 'status': response.status_code, 'code': code}
                    # Provider prose can contain identities or request values.
                    # Only a bounded code and our own stage labels are displayed.
                    if response.status_code == 429:
                        error=ConnectionError('Jio has rate-limited this request. Wait before retrying.')
                        error.status=response.status_code
                        raise error
                    suffix = f', code {code}' if code else ''
                    error=ConnectionError(f'Jio rejected {request_stage(url)} (HTTP {response.status_code}{suffix}). No upload was attempted.')
                    error.status=response.status_code
                    raise error
                if not isinstance(data, dict):
                    raise ConnectionError('Jio returned an unsupported response format.')
                if data.get('error') or data.get('errorCode'):
                    raise ConnectionError('Jio rejected the request. Check your account details or OTP.')
                return data
        except (requests.RequestException, ValueError) as exc:
            if isinstance(exc, ConnectionError):
                raise
            raise ConnectionError('Could not complete the Jio connection request. Please retry.') from None

    def configure(self):
        if self.headers:
            return
        data = self.request('GET', PUBLIC_CONFIG).get('envHeaders', {})
        if not all(isinstance(data.get(k), str) and 1 <= len(data[k]) <= 512
                   and '\r' not in data[k] and '\n' not in data[k]
                   for k in ('X-Api-Key', 'X-App-Secret')):
            raise ConnectionError('The Jio website configuration changed. Its connector needs updating.')
        self.headers = {k: data[k] for k in ('X-Api-Key', 'X-App-Secret')}
        self.headers.update({'X-Client-Details': 'clientType:WEB; appVersion:3.0.0',
                             'Content-Type': 'application/json; charset=UTF-8',
                             'Accept': 'application/json', 'Accept-Language': 'en', 'X-Device-Type': 'W'})

    def send_otp(self, identity):
        if time.monotonic() - self.last_otp < 60:
            raise ConnectionError('Please wait 60 seconds before requesting another OTP.')
        who = login_identity(identity)
        self.configure()
        self.last_otp = time.monotonic()
        self.identity = None
        self.session = {}
        self.profile = {}
        self.candidates = []
        self.destination = None
        self.request('POST', SECURITY + '/account/login/otp/send',
                     {k: v for k, v in who.items() if v})
        self.identity = who
        self.attempts = 0
        self.message = 'OTP requested. Enter it here; do not send it in chat.'

    def reset_login(self):
        """Discard rejected in-memory credentials; preserve the encrypted recovery file."""
        self.session = {}
        self.identity = None
        self.profile = {}
        self.candidates = []
        self.destination = None
        self.last_error = {}
        self.message = 'Enter your account and request a fresh OTP to reconnect.'

    def login(self, otp, user_agent=''):
        if self.session.get('twoFAValidated'):
            # An accepted OTP must not be submitted again just because the
            # subsequent profile/folder GET failed.
            return self.inspect()
        if not self.identity or self.attempts >= 5:
            raise ConnectionError('Request a new OTP before continuing.')
        if not re.fullmatch(r'\d{6}', str(otp).strip()):
            raise ConnectionError('Enter the six-digit OTP sent by Jio.')
        self.attempts += 1
        browser, version = browser_details(user_agent)
        result = self.request('POST', SECURITY + '/account/otp/login', {
            **self.identity, 'otp': str(otp).strip(), 'deviceType': 'W', 'isStaySignIn': True,
            'deviceInfo': {'model': 'browser', 'deviceName': 'Web Device', 'platformType': browser,
                           'platformVersion': version, 'type': 'browser', 'isWebClient': True}})
        if result.get('recoverData'):
            raise ConnectionError('Complete account recovery on JioAICloud before connecting Sakura.')
        if not result.get('authToken', {}).get('accessToken') or not result.get('userId'):
            raise ConnectionError('Jio did not return a complete login session.')
        # Keep only required connection fields, not the provider's entire response.
        self.session = {k: result[k] for k in ('authToken', 'userId', 'deviceKey', 'dcGroupCode',
                                              'rootFolderKey', 'isTwoFAEnabled', 'encTwoFASessionKey')
                        if k in result}
        self.session.setdefault('deviceKey', str(uuid.uuid4()))
        self.identity = None
        if (str(self.session.get('isTwoFAEnabled', '')).upper() in ('Y', 'TRUE', '1')
                or self.session.get('encTwoFASessionKey')):
            self.message = 'Your account requires its Jio passphrase to complete login.'
            return
        self.session['twoFAValidated'] = True
        self.message = f'OTP accepted. Checking the account and {self.folder_name} folder.'
        self.inspect()

    def unlock(self, passphrase):
        if not self.session.get('encTwoFASessionKey') or not isinstance(passphrase, str) or not 1 <= len(passphrase) <= 512:
            raise ConnectionError('A Jio passphrase challenge is not available. Reconnect.')
        proof = two_fa_header(self.session['userId'], passphrase, self.session['encTwoFASessionKey'])
        self.request('GET', SECURITY + '/2fa/validation', authenticated=True, extra={'X-Enc-2FAHash': proof})
        self.session['twoFAValidated'] = True
        self.inspect()

    def inspect(self, preserve_destination=False):
        if not self.session.get('twoFAValidated'):
            raise ConnectionError('Complete Jio login before checking the destination.')
        self.profile = {}
        self.candidates = []
        self.destination = None
        profile = self.request('GET', SECURITY + '/security/users', authenticated=True)
        if profile.get('userId') != self.session['userId']:
            raise ConnectionError('Jio account identity could not be verified. Nothing was saved or uploaded.')
        self.profile = {k: profile.get(k, '') for k in ('userId', 'emailId', 'mobileNumber', 'firstName', 'lastName')}
        for key in ('rootFolderKey', 'dcGroupCode'):
            if profile.get(key):
                self.session[key] = profile[key]
        # Preserve the verified login across connector updates without granting
        # any upload destination. Confirmation is a separate explicit action.
        previous=self.store.load().get('destination') if preserve_destination else None
        self.store.save({'session': self.session, 'destination': previous, 'folder_name':self.folder_name})
        code = self.session.get('dcGroupCode')
        root = self.session.get('rootFolderKey')
        if code not in REGIONS or not isinstance(root, str) or not root:
            raise ConnectionError('Jio did not provide a supported region and root folder. Nothing was uploaded.')
        origin = f'https://{REGIONS[code]}-api.jioaicloud.com'
        # The official web client uses type=w for folders, type=f for files.
        # Match the website's folder picker, including its explicit sort.
        # NMS also requires Accept-Language (configured in the common headers).
        path = '/nms/metadata?' + urlencode({'limit': 2000, 'folderKey': root,
                                             'sort': '+objectName', 'type': 'w'})
        url = origin + path
        seen = set()
        for _ in range(50):
            if url in seen:
                raise ConnectionError('Jio repeated a folder listing page. Destination verification stopped.')
            seen.add(url)
            if not (url.startswith(origin + '/nms/metadata/') or url.startswith(origin + '/nms/metadata?')):
                raise ConnectionError('Jio returned an unexpected folder listing address.')
            page = self.request('GET', url, authenticated=True)
            objects = page.get('objects', page.get('files'))
            if not isinstance(objects, list):
                raise ConnectionError('Jio returned an unsupported folder listing format.')
            for item in objects:
                if not isinstance(item, dict) or str(item.get('objectName', '')).casefold() != self.folder_name.casefold():
                    continue
                if isinstance(item.get('objectKey'), str) and item['objectKey']:
                    self.candidates.append({'id': item['objectKey'], 'name': item['objectName']})
            next_link = page.get('nextLink')
            if not next_link:
                break
            if not isinstance(next_link, str):
                raise ConnectionError('Jio returned invalid folder pagination.')
            url = origin + next_link if next_link.startswith('/') and not next_link.startswith('//') else next_link
        else:
            raise ConnectionError('Jio folder listing exceeded 50 pages. Destination verification stopped.')
        if len(self.candidates) == 1:
            self.message = f'Account verified. Confirm that this account and its {self.folder_name} folder are correct.'
        elif self.candidates:
            self.message = f'Multiple {self.folder_name} folders were found. No destination was selected; resolve this before uploading.'
        else:
            self.message = f'No {self.folder_name} folder found in My Files. Check the account and create it there, then refresh.'
        self.last_error = {}

    def resume(self):
        saved = self.store.load()
        if not self.explicit_folder:self.folder_name=saved.get('folder_name','live2d')
        session = saved.get('session', {})
        if not isinstance(session, dict) or not session.get('twoFAValidated'):
            return
        self.configure()
        self.session = session
        self.message = f'Restored the encrypted Jio login. Checking your account and {self.folder_name} folder.'
        try:
            self.inspect(preserve_destination=True)
        except ConnectionError:
            if self.last_error.get('status') not in (401,403) or not session.get('authToken',{}).get('refreshToken'):
                raise
            value=self.request('PUT',SECURITY+'/account/token/refresh',
                {'refreshToken':session['authToken']['refreshToken'],'deviceType':'W','jToken':True,
                 'isIdamOn':'true','isStaySignIn':True,'deviceInfo':{'model':'browser','deviceName':'Web Device',
                 'type':'browser','isWebClient':True,'deviceKey':session['deviceKey']}},authenticated=True)
            token=value.get('authToken',value)
            if not isinstance(token.get('accessToken'),str) or not token['accessToken']:
                raise ConnectionError('Jio needs a fresh owner sign-in.')
            session['authToken'].update({k:token[k] for k in ('accessToken','refreshToken','expiresIn') if k in token})
            self.inspect(preserve_destination=True)
        destination = saved.get('destination')
        if (isinstance(destination, dict) and len(self.candidates) == 1
                and destination.get('userId') == self.profile.get('userId')
                and destination.get('folderKey') == self.candidates[0]['id']):
            self.destination = destination
            self.store.save({'session': self.session, 'destination': self.destination, 'folder_name':self.folder_name})
            self.message = f'Connected to the verified account and My Files / {self.folder_name}. No files uploaded yet.'
        else:
            self.store.save({'session':self.session,'destination':None,'folder_name':self.folder_name})

    def confirm(self):
        if not self.profile or len(self.candidates) != 1 or not self.session.get('twoFAValidated'):
            raise ConnectionError(f'Verify the account and one existing {self.folder_name} folder first.')
        self.destination = {'folderKey': self.candidates[0]['id'], 'name': self.candidates[0]['name'],
                            'userId': self.profile['userId'], 'confirmedAt': int(time.time())}
        self.store.save({'session': self.session, 'destination': self.destination, 'folder_name':self.folder_name})
        self.message = f'Connection saved with Windows encryption. Destination: My Files / {self.folder_name}. No files uploaded yet.'

    def public(self):
        return {'message': self.message, 'otpRequested': bool(self.identity),
                'otpAccepted': bool(self.session.get('authToken')),
                'needsPassphrase': bool(self.session) and not self.session.get('twoFAValidated', False),
                'canInspect': bool(self.session.get('twoFAValidated')),
                'lastError': self.last_error,
                'account': {k: v for k, v in self.profile.items() if k != 'userId'},
                'folderCount': len(self.candidates),
                'folder': self.candidates[0]['name'] if len(self.candidates) == 1 else '',
                'connected': bool(self.destination)}


PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Sakura — JioAICloud owner connection</title><style>
body{background:#11161d;color:#e7edf5;font:16px system-ui;margin:0;padding:30px}main{max-width:590px;margin:30px auto;background:#202832;border:1px solid #475362;border-radius:18px;padding:28px}h1{font-size:25px}p{line-height:1.5}label{display:block;margin:18px 0 8px}input,button{box-sizing:border-box;font:inherit;border-radius:8px;padding:12px;border:1px solid #718397}input{width:100%;background:#11161d;color:white}button{background:#a9d8ff;color:#102333;cursor:pointer;margin:12px 8px 0 0}button:disabled{opacity:.5;cursor:wait}section{border-top:1px solid #475362;margin-top:22px;padding-top:14px}#message{background:#11161d;padding:14px;border-radius:9px;white-space:pre-wrap}small{color:#bcc9d8}[hidden]{display:none!important}</style>
<main><small>SAKURA · OWNER SETUP · THIS PC ONLY</small><h1>Connect JioAICloud</h1>
<p>Use the account containing your <strong>Live2d</strong> folder. This page checks the account and folder; it does not upload or publish models. Verified login is saved with Windows encryption so folder-check retries do not need another OTP.</p>
<div id="message" role="status">Ready.</div><button id="restart-login" type="button">Sign in again</button>
<form id="send"><label for="identity">JioAICloud email or mobile number</label><input id="identity" autocomplete="username" required maxlength="250"><button>Send OTP</button></form>
<form id="verify" hidden><label for="otp">OTP from Jio</label><input id="otp" autocomplete="one-time-code" inputmode="numeric" maxlength="6" minlength="6" required><button>Verify OTP</button></form>
<form id="unlock" hidden><label for="passphrase">Jio account passphrase</label><input id="passphrase" type="password" autocomplete="current-password" maxlength="512" required><button>Unlock account</button><p><small>The passphrase is used for Jio's challenge and is not saved.</small></p></form>
<section id="account" hidden><h2>Verify the destination</h2><p id="who"></p><p id="folder"></p><button id="refresh">Retry account / folder check</button><button id="confirm" hidden>Use this account and live2d folder</button></section>
<p><small>Enter credentials only on this local page. Do not send OTPs, passphrases or tokens in chat. Your Chrome login is not read. Close this page when finished; setup expires after 30 minutes.</small></p></main>
<script>
const capability=location.hash.slice(1)||sessionStorage.getItem('sakura-owner-capability')||'';
if(capability)sessionStorage.setItem('sakura-owner-capability',capability);
history.replaceState(null,'',location.pathname);
const el=id=>document.getElementById(id);
function render(s){el('message').textContent=s.message;el('send').hidden=!!s.otpAccepted;el('verify').hidden=!s.otpRequested||s.otpAccepted;el('unlock').hidden=!s.needsPassphrase;const a=s.account||{};el('account').hidden=!s.canInspect&&!Object.keys(a).length;el('who').textContent=[a.firstName,a.lastName,a.emailId,a.mobileNumber].filter(Boolean).join(' · ');el('folder').textContent=s.folder?'Destination: My Files / '+s.folder:'Matching live2d folders: '+s.folderCount;el('confirm').hidden=s.folderCount!==1||s.connected;}
async function call(action,body={}){const buttons=document.querySelectorAll('button');buttons.forEach(b=>b.disabled=true);try{const r=await fetch('/api/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-Sakura-Owner':capability},body:JSON.stringify(body)});const s=await r.json();if(!r.ok){if(s.state)render(s.state);throw Error(s.error||'Connection request failed.');}render(s);}catch(e){el('message').textContent=e.message;}finally{buttons.forEach(b=>b.disabled=false);}}
el('send').onsubmit=e=>{e.preventDefault();call('send-otp',{identity:el('identity').value});};
el('verify').onsubmit=e=>{e.preventDefault();const otp=el('otp').value;el('otp').value='';call('verify-otp',{otp});};
el('unlock').onsubmit=e=>{e.preventDefault();const passphrase=el('passphrase').value;el('passphrase').value='';call('unlock',{passphrase});};
el('refresh').onclick=()=>call('inspect');el('confirm').onclick=()=>call('confirm');call('status');
el('restart-login').onclick=()=>call('reset-login');
</script></html>'''


def make_server(connection, token=None):
    capability = token or secrets.token_urlsafe(32)
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log OTP payloads, identities or capability URLs.

        def trusted_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def respond(self, status, value, html=False):
            raw = value.encode() if html else json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8' if html else 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if not self.trusted_host() or self.path != '/':
                return self.respond(404, {'error': 'Not found.'})
            self.respond(200, PAGE.replace('live2d',connection.folder_name).replace('Live2d',connection.folder_name), html=True)

        def do_POST(self):
            origin = f'http://127.0.0.1:{self.server.server_port}'
            if (not self.trusted_host() or not secrets.compare_digest(self.headers.get('X-Sakura-Owner', ''), capability)
                    or self.headers.get('Origin') not in (None, origin)):
                return self.respond(403, {'error': 'Open the owner setup page launched on this PC.'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 4096 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    return self.respond(400, {'error': 'Invalid request.'})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    return self.respond(400, {'error': 'Invalid request.'})
                with lock:
                    if self.path == '/api/send-otp':
                        connection.send_otp(body.get('identity', ''))
                    elif self.path == '/api/verify-otp':
                        connection.login(body.get('otp', ''), self.headers.get('User-Agent', ''))
                    elif self.path == '/api/unlock':
                        connection.unlock(body.get('passphrase', ''))
                    elif self.path == '/api/inspect':
                        connection.inspect()
                    elif self.path == '/api/confirm':
                        connection.confirm()
                    elif self.path == '/api/reset-login':
                        connection.reset_login()
                    elif self.path != '/api/status':
                        return self.respond(404, {'error': 'Not found.'})
                    value = connection.public()
                self.respond(200, value)
            except ConnectionError as exc:
                # Make failures diagnosable without logging accounts or OTPs.
                if connection.last_error:
                    expired = connection.last_error.get('status') in (401,403)
                    diagnostic = Path(__file__).resolve().parents[1] / 'audit-results/jio-integration/last-error.json'
                    try:
                        diagnostic.parent.mkdir(parents=True, exist_ok=True)
                        diagnostic.write_text(json.dumps({**connection.last_error, 'at': int(time.time())}), encoding='utf-8')
                    except OSError:
                        pass
                    if expired:
                        connection.reset_login()
                self.respond(400, {'error': str(exc), 'state': connection.public()})
            except Exception:
                self.respond(400, {'error': 'Could not complete the connection check. Nothing was uploaded.'})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    return server, f'http://127.0.0.1:{server.server_port}/#{capability}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--account',choices=['primary','account2'],default='primary')
    parser.add_argument('--folder',choices=['Live2d','PMX'],default='Live2d')
    args = parser.parse_args()
    os.environ['SAKURA_JIO_ACCOUNT']=args.account
    connection = JioConnection(folder_name=args.folder)
    try:
        connection.resume()
    except ConnectionError as exc:
        if connection.last_error.get('status') in (401,403):
            connection.reset_login()
        connection.message = str(exc)
    server, url = make_server(connection)
    print('Connecting '+args.account+' in its separate encrypted profile; expected folder: '+args.folder,flush=True)
    timer = threading.Timer(1800, server.shutdown)
    timer.daemon = True
    timer.start()
    if not args.no_browser:
        webbrowser.open(url)
    print('Owner setup is open on this PC. It expires in 30 minutes. No uploads are enabled.', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        timer.cancel()


if __name__ == '__main__':
    main()
