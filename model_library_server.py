"""Private catalogue host. Run behind HTTPS; never ship owner files in an installer.

SAKURA_LIBRARY_ROOT points to publisher output; SAKURA_LIBRARY_MEMBERS points to
a private JSON object mapping member names to SHA256 hashes of random access codes.
There are no public file mounts, upload routes or Drive credentials in this service.
"""
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
import requests

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse


def create_app(root=None, members_file=None):
    root = Path(root or os.environ.get('SAKURA_LIBRARY_ROOT', 'private-model-library')).resolve()
    members_file = Path(members_file or os.environ.get('SAKURA_LIBRARY_MEMBERS', 'private-library-members.json'))
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def supabase(path, payload=None, token=None):
        endpoint = os.environ.get('SAKURA_LIBRARY_SUPABASE_URL', '').rstrip('/')
        key = os.environ.get('SAKURA_LIBRARY_SUPABASE_PUBLISHABLE_KEY', '')
        if not endpoint.startswith('https://') or not key:
            raise HTTPException(503, 'Sakura account registration is not configured yet.')
        headers = {'apikey': key}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        try:
            response = requests.request('GET' if payload is None else 'POST', endpoint + '/auth/v1/' + path,
                json=payload, headers=headers, timeout=(5, 15), allow_redirects=False)
        except requests.RequestException:
            raise HTTPException(503, 'Account service is unavailable. Try again later.')
        if response.status_code not in (200, 201):
            raise HTTPException(401, 'Sign-in failed. Check your details and email confirmation.')
        return response.json()

    @app.middleware('http')
    async def authenticate(request: Request, call_next):
        from fastapi.responses import JSONResponse
        if request.method == 'POST' and request.url.path in {'/v1/auth/signin', '/v1/auth/signup', '/v1/auth/refresh'}:
            response = await call_next(request)
            response.headers['Cache-Control'] = 'no-store'
            return response
        header = request.headers.get('authorization', '')
        token = header[7:] if header.startswith('Bearer ') else ''
        try:
            members = json.loads(members_file.read_text(encoding='utf-8'))
            digest = hashlib.sha256(token.encode()).hexdigest()
            allowed = bool(re.fullmatch('[A-Za-z0-9_-]{32,256}', token)) and any(
                isinstance(value, str) and hmac.compare_digest(digest, value) for value in members.values())
        except (OSError, ValueError, AttributeError, TypeError):
            allowed = False
        if not allowed and 32 <= len(token) <= 8192 and os.environ.get('SAKURA_LIBRARY_SUPABASE_URL'):
            # Verify with Auth, including expiry/revocation. Never trust decoded JWT claims alone.
            from starlette.concurrency import run_in_threadpool
            try:
                user = await run_in_threadpool(supabase, 'user', token=token)
                allowed = bool(user.get('id') and user.get('email_confirmed_at'))
            except HTTPException:
                allowed = False
        if not allowed:
            return JSONResponse({'error': 'Sakura library access required.'}, 401, headers={'Cache-Control': 'no-store'})
        response = await call_next(request)
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.post('/v1/auth/{action}')
    async def account(action: str, request: Request):
        from starlette.concurrency import run_in_threadpool
        if action not in ('signin', 'signup', 'refresh'):
            raise HTTPException(404)
        raw = await request.body()
        if len(raw) > 16384:
            raise HTTPException(400, 'Account request is too large.')
        try:
            body = json.loads(raw)
        except ValueError:
            raise HTTPException(400, 'Invalid account request.')
        if not isinstance(body, dict):
            raise HTTPException(400, 'Invalid account request.')
        if action == 'refresh':
            token = body.get('refresh_token')
            if not isinstance(token, str) or not 10 <= len(token) <= 8192:
                raise HTTPException(400, 'Sign in again.')
            path, payload = 'token?grant_type=refresh_token', {'refresh_token': token}
        else:
            email, password = body.get('email'), body.get('password')
            if not isinstance(email, str) or '@' not in email or len(email) > 254 or not isinstance(password, str) or not 8 <= len(password) <= 256:
                raise HTTPException(400, 'Enter an email address and password of at least 8 characters.')
            path = 'signup' if action == 'signup' else 'token?grant_type=password'
            payload = {'email': email, 'password': password}
        data = await run_in_threadpool(supabase, path, payload)
        if not data.get('access_token'):
            return {'confirmation_required': True, 'message': 'Check your email to confirm your Sakura account, then sign in.'}
        return {key: data.get(key) for key in ('access_token', 'refresh_token', 'expires_in')}

    def catalogue():
        try:
            return json.loads((root / 'catalogue.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            raise HTTPException(503, 'Library is not published yet.')

    @app.get('/v1/models')
    def models():
        return catalogue()

    @app.get('/v1/models/{identifier}/package')
    def package(identifier: str):
        if not re.fullmatch('[a-zA-Z0-9_-]{1,100}', identifier):
            raise HTTPException(404)
        entry = next((m for m in catalogue().get('models', []) if m.get('id') == identifier), None)
        path = root / (identifier + '.zip')
        if not entry or not path.is_file() or not path.resolve().is_relative_to(root):
            raise HTTPException(404)
        return FileResponse(path, media_type='application/zip', filename=identifier + '.zip')

    @app.get('/v1/models/{identifier}/preview')
    def preview(identifier: str):
        if not re.fullmatch('[a-zA-Z0-9_-]{1,100}',identifier):raise HTTPException(404)
        entry=next((m for m in catalogue().get('models',[]) if m.get('id')==identifier),None)
        path=root/(identifier+'.webp')
        if not entry or not entry.get('preview') or not path.is_file() or not path.resolve().is_relative_to(root):
            raise HTTPException(404)
        if path.stat().st_size>8_000_000:raise HTTPException(413)
        return FileResponse(path,media_type='image/webp')

    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(create_app(), host='127.0.0.1', port=8788)
