"""Private model-library client. Owner storage credentials never enter the app."""
import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

from model_import import MAX_BYTES, import_package
from model_library_config import SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, LIBRARY_URL

ID = re.compile(r'^[a-zA-Z0-9_-]{1,100}$')
# Supabase writes this address into both emailed links, and the companion port only rolls
# forward when something else already holds it.
LINK_PORT = 8766
UNREADABLE = 'Sakura could not read the answer from the account service. Try again, and if it keeps happening check the library address with its owner.'
_install_lock = threading.Lock()


class AccountError(ValueError):
    """A safe, actionable account message; never includes provider response data."""


def account_error(response):
    try:
        code = response.json().get('error_code') or response.json().get('code')
    except (ValueError, AttributeError):
        code = None
    messages = {
        'email_address_not_authorized': 'Account registration is waiting for the Sakura owner to configure a verification-email sender. Supabase currently only sends to project-team addresses.',
        'over_email_send_rate_limit': 'Too many verification emails were requested. Wait before trying again. The Sakura owner may need to configure the email sender.',
        'over_request_rate_limit': 'Too many account requests. Please wait a few minutes and try again.',
        'email_not_confirmed': 'Confirm your email using the verification email before signing in. Check your spam folder too.',
        'invalid_credentials': 'The email or password is incorrect. If you do not have a Sakura account yet, choose Create account.',
        'user_already_exists': 'This email already has an account. Choose Sign in instead.',
        'weak_password': 'Choose a stronger password with at least 8 characters, including letters, numbers and a symbol.',
        'email_address_invalid': 'Enter a valid email address.',
        'signup_disabled': 'New Sakura account registration is currently disabled by the owner.',
        'email_provider_disabled': 'Email sign-in is currently disabled by the owner.',
        'captcha_failed': 'Account verification needs attention. Please contact the Sakura owner.',
        'unexpected_failure': 'The account service could not finish registration. The Sakura owner should check the verification-email sender and Supabase Auth logs.',
    }
    if code in messages:
        return AccountError(messages[code])
    if response.status_code == 429:
        return AccountError('Too many account requests. Please wait before trying again.')
    return AccountError('The account service refused the request. Check your email and password, or ask the Sakura owner to check the Auth logs.')


def library_url(value):
    value = str(value or '').strip().rstrip('/')
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost', '::1'})) or not parsed.hostname:
        raise ValueError('Use the HTTPS address of the Sakura library service.')
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/', '/functions/v1/sakura-library'):
        raise ValueError('Use the library service address without a path, password or query.')
    return value


class ModelLibrary:
    def __init__(self, root, configuration, transport=requests):
        self.root = Path(root)
        self.configuration = configuration
        self.transport = transport

    def _request(self, path):
        config = self.configuration()
        endpoint = library_url(config.get('url'))
        token = str(config.get('token') or '')
        if not token:
            raise ValueError('Connect to the Sakura library with your access code first.')
        headers = {'Authorization': 'Bearer ' + token}
        if endpoint == LIBRARY_URL:
            headers['apikey'] = SUPABASE_PUBLISHABLE_KEY
        response = self.transport.get(endpoint + path, headers=headers,
                                      timeout=(8, 120), stream=True, allow_redirects=False)
        if response.status_code != 200:
            response.close()
            if response.status_code in (401, 403):
                raise ValueError('Library access was refused. Check your access code with the library owner.')
            raise ValueError('The model library could not complete this request. Try again later.')
        return response

    def catalogue(self):
        with self._request('/v1/models') as response:
            raw = bytearray()
            for chunk in response.iter_content(65536):
                raw.extend(chunk)
                if len(raw) > 2_000_000:
                    raise ValueError('The library catalogue is too large.')
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get('models'), list) or len(data['models']) > 2000:
            raise ValueError('Invalid model library catalogue.')
        models = []
        for entry in data['models']:
            if not isinstance(entry, dict) or not ID.fullmatch(str(entry.get('id', ''))):
                raise ValueError('Invalid library model identifier.')
            if entry.get('format') not in {'pmx', 'vrm', 'live2d'} or not re.fullmatch('[a-f0-9]{64}', str(entry.get('sha256', ''))):
                raise ValueError('Invalid library model metadata.')
            size = entry.get('bytes')
            if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= MAX_BYTES:
                raise ValueError('Model packages must be under 512 MB.')
            record = self._installed(entry['id'])
            models.append({key: entry.get(key) for key in ('id', 'name', 'format', 'bytes', 'sha256', 'version', 'mobile_compatible')}
                          | {'installed': bool(record and record.get('sha256') == entry['sha256'])})
        return {'models': models}

    def _installed(self, identifier):
        try:
            record = json.loads((self.root / '.library' / (identifier + '.json')).read_text(encoding='utf-8'))
            if record.get('models') and all((self.root / p).is_file() and (self.root / p).resolve().is_relative_to(self.root.resolve()) for p in record['models']):
                return record
        except (OSError, ValueError, TypeError):
            pass
        return None

    def install(self, identifier):
        if not ID.fullmatch(str(identifier)):
            raise ValueError('Choose a model from the library.')
        # Serialize imports to avoid duplicate packages from repeated clicks/windows.
        with _install_lock:
            entry = next((m for m in self.catalogue()['models'] if m['id'] == identifier), None)
            if entry is None:
                raise ValueError('This model is no longer listed in the library.')
            old = self._installed(identifier)
            if old:
                # Updating replaces neither user edits nor an existing character.
                return {'ok': True, 'models': old['models'], 'already_installed': True,
                        'message': 'Already installed. Your existing character and edits were kept.'}
            with self._request('/v1/models/' + identifier + '/package') as response:
                content = bytearray()
                digest = hashlib.sha256()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    digest.update(chunk)
                    if len(content) > entry['bytes'] or len(content) > MAX_BYTES:
                        raise ValueError('The download exceeded its declared size.')
            if len(content) != entry['bytes'] or digest.hexdigest() != entry['sha256']:
                raise ValueError('The model download failed its integrity check. Nothing was installed.')
            result = import_package(self.root, [('library.zip', content)], entry['format'])
            record = {**entry, 'models': result['models']}
            folder = self.root / '.library'
            folder.mkdir(exist_ok=True)
            temporary = folder / (identifier + '.tmp')
            temporary.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
            temporary.replace(folder / (identifier + '.json'))
            return {'ok': True, **result}


def router(root, local_check):
    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse
    from starlette.concurrency import run_in_threadpool
    from agent_connections import secret_get, secret_set
    from model_library_confirm import reset_pending

    routes = APIRouter(prefix='/api/model-library')
    session_lock = threading.Lock()

    def link_warning(request):
        """Warn out loud when an emailed link cannot land, rather than letting it fail silently."""
        port = request.url.port or (443 if request.url.scheme == 'https' else 80)
        if port == LINK_PORT:
            return ''
        return (' Sakura is reachable on port ' + str(port) + ' instead of ' + str(LINK_PORT) + ' right now, so the link in that email'
                ' will open nothing on this computer. Close whatever uses ' + str(LINK_PORT) + ', restart Sakura, then request a fresh email.')

    def auth_call(endpoint, action, body):
        # Direct managed Auth avoids routing passwords through a model-file host.
        if endpoint == LIBRARY_URL:
            path = {'signin': '/token?grant_type=password', 'signup': '/signup', 'recover': '/recover',
                    'refresh': '/token?grant_type=refresh_token'}[action]
            target = SUPABASE_URL + '/auth/v1' + path
            headers = {'apikey': SUPABASE_PUBLISHABLE_KEY}
        else:
            target, headers = endpoint + '/v1/auth/' + action, {}
        with requests.post(target, json=body, headers=headers, timeout=(8, 30), allow_redirects=False) as response:
            if response.status_code not in (200, 201):
                raise account_error(response)
            data = response.json()
        if action == 'recover':
            # Auth replies the same way whether or not the address has an account, so the
            # wording must not confirm either case.
            return {'reset_sent': True, 'message': 'If that email has a Sakura account, a reset link is on its way. Check your inbox and your spam folder.'
                        ' Open the link on this computer and choose the new password there: Sakura keeps using your old password until you press Set new password.'}
        # A refresh must always carry a session, so only a sign-up or sign-in answer may read as
        # "confirm your email first".
        if action != 'refresh' and (data.get('confirmation_required') or (endpoint == LIBRARY_URL and not data.get('access_token'))):
            return {'confirmation_required': True, 'message': 'Check your email to confirm your Sakura account, then sign in.'}
        # Callers read these three keys to build the saved session, so a host that answers 200 with
        # anything else must be reported as the library's fault instead of a guessed password or a
        # crash on the missing key.
        if not data.get('access_token'):
            raise AccountError('The library service answered the sign-in without a session. If you have not confirmed your email address yet, use the link in the confirmation email and try again.')
        try:
            expires_in = int(data.get('expires_in'))
        except (TypeError, ValueError):
            expires_in = 0
        if not data.get('refresh_token') or expires_in <= 0:
            raise AccountError('The library service returned an incomplete session, so Sakura could not keep you signed in. Check the library address with its owner.')
        return data

    def configuration():
        with session_lock:
            config = secret_get('model-library')
            if config.get('refresh_token') and config.get('expires_at', 0) < time.time() + 30:
                data = auth_call(library_url(config['url']), 'refresh', {'refresh_token': config['refresh_token']})
                config.update(token=data['access_token'], refresh_token=data['refresh_token'], expires_at=time.time() + int(data['expires_in']))
                secret_set('model-library', config)
            return config

    client = ModelLibrary(root, configuration)

    @routes.post('/account/{action}')
    async def account(action: str, request: Request):
        if not local_check(request):
            return JSONResponse({'error': 'Use Sakura on this computer.'}, 403)
        if action not in ('signin', 'signup', 'recover'):
            return JSONResponse({'error': 'Unknown account action.'}, 400)
        # The reset hint below may run before the body is read, so it needs a value either way.
        email = None
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise AccountError('Enter your email and password.')
            try:
                endpoint = library_url(body.get('url') or LIBRARY_URL)
            except ValueError as exc:
                # The address check already says what is wrong with the address, and a password
                # reminder would bury it.
                raise AccountError(str(exc))
            email, password = body.get('email'), body.get('password')
            email = email.strip() if isinstance(email, str) else email
            if action == 'recover':
                if not isinstance(email, str) or '@' not in email or len(email) > 254:
                    raise AccountError('Enter the email address you created your Sakura account with.')
                payload = {'email': email}
            else:
                if not isinstance(email, str) or '@' not in email or len(email) > 254 or not isinstance(password, str) or not 8 <= len(password) <= 256:
                    raise AccountError('Enter a valid email address and a password of at least 8 characters, then choose Create account or Sign in.')
                payload = {'email': email, 'password': password}
            data = await run_in_threadpool(auth_call, endpoint, action, payload)
            # Neither of these answers carries a session, so neither may touch the saved one.
            if data.get('confirmation_required') or data.get('reset_sent'):
                warning = link_warning(request)
                return {**data, 'message': data['message'] + warning} if warning else data
            candidate = {'url': endpoint, 'token': data['access_token'], 'refresh_token': data['refresh_token'],
                         'expires_at': time.time() + int(data['expires_in'])}
            if endpoint != LIBRARY_URL:
                try:
                    await run_in_threadpool(ModelLibrary(root, lambda: candidate).catalogue)
                except ValueError as exc:
                    raise AccountError(str(exc))
            secret_set('model-library', candidate)
            return {'ok': True}
        except AccountError as exc:
            text = str(exc)
            # A reset link the user has opened but not finished looks exactly like a wrong
            # password from here, so say which of the two it is while the link still waits.
            if action == 'signin' and isinstance(email, str) and reset_pending(email):
                text += (' You have a reset link open on this computer that has not been finished yet:'
                         ' choose the new password on that page and press Set new password, then sign in with it.')
            return JSONResponse({'error': text}, 400)
        except requests.exceptions.JSONDecodeError:
            # A reply that is not JSON means the service is reachable and confused, which is a
            # different thing to tell the user from a network that is not there at all.
            return JSONResponse({'error': UNREADABLE}, 400)
        except requests.RequestException:
            return JSONResponse({'error': 'Cannot reach Sakura accounts. Check your internet connection and try again.'}, 503)
        except (ValueError, KeyError, TypeError):
            return JSONResponse({'error': UNREADABLE}, 400)

    @routes.get('/connection')
    async def connection(request: Request):
        if not local_check(request):
            return JSONResponse({'error': 'Use Sakura on this computer.'}, 403)
        config = secret_get('model-library')
        return {'configured': bool(config.get('url') and config.get('token')),
                'url': config.get('url') or os.environ.get('SAKURA_MODEL_LIBRARY_URL') or LIBRARY_URL,
                # Access codes only work against a library the owner hosts; the panel needs to know
                # which address is the Sakura cloud so it stops offering a code there.
                'cloud': LIBRARY_URL}

    @routes.post('/connection')
    async def configure(request: Request):
        if not local_check(request):
            return JSONResponse({'error': 'Use Sakura on this computer.'}, 403)
        try:
            body = await request.json()
            if body.get('disconnect') is True:
                secret_set('model-library', {})
                return {'ok': True, 'configured': False}
            endpoint = library_url(body.get('url'))
            token = str(body.get('token') or '').strip()
            if not re.fullmatch('[A-Za-z0-9_-]{32,256}', token):
                raise ValueError('Enter the library access code provided by its owner.')
            candidate = ModelLibrary(root, lambda: {'url': endpoint, 'token': token})
            await run_in_threadpool(candidate.catalogue)
            secret_set('model-library', {'url': endpoint, 'token': token})
            return {'ok': True, 'configured': True}
        except (ValueError, requests.RequestException):
            return JSONResponse({'error': 'Could not connect. Check the library address and access code.'}, 400)

    @routes.get('/models')
    async def models(request: Request):
        if not local_check(request):
            return JSONResponse({'error': 'Use Sakura on this computer.'}, 403)
        try:
            return await run_in_threadpool(client.catalogue)
        except (ValueError, requests.RequestException):
            return JSONResponse({'error': 'Cannot read the library. Check your connection and access code.'}, 400)

    @routes.post('/models/{identifier}/install')
    async def install(identifier: str, request: Request):
        if not local_check(request):
            return JSONResponse({'error': 'Use Sakura on this computer.'}, 403)
        try:
            return await run_in_threadpool(client.install, identifier)
        except (ValueError, requests.RequestException, OSError):
            return JSONResponse({'error': 'Installation failed. Check access, free space and the model package. Your existing models were kept.'}, 400)

    return routes
