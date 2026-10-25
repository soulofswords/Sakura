"""Spend the Supabase email-confirmation token when the user clicks the link in their mailbox.

Sakura is a desktop app, so the verification link Supabase embeds in its email has nowhere to
land: the token must be posted back to Auth before the account becomes confirmed and sign-in works.
"""
import re

import requests

from model_library_config import SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY

PARAMS = ('confirmation_token', 'verification_token', 'token', 'otp')
TOKEN = re.compile(r'^[A-Za-z0-9_-]{6,512}$')
ONE_TIME_PASSWORD = re.compile(r'^\d{4,10}$')
ALREADY_USED = re.compile(r'\balready\b', re.I)
CONFIRM_ENDPOINT = SUPABASE_URL + '/auth/v1/verify'
HEADERS = {'Cache-Control': 'no-store', 'X-Frame-Options': 'SAMEORIGIN',
           'Referrer-Policy': 'no-referrer', 'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'"}
# Visiting the page without a token is normal history noise, not an error; only a spent or
# unreachable confirmation answers with a failure status.
STATUS = {'confirmed': 200, 'already': 200, 'absent': 200, 'invalid': 400, 'offline': 503, 'foreign': 403}

MESSAGES = {
    'confirmed': ('🌸', 'Your email address is confirmed.',
                  'Go back to Sakura and choose Sign in with the same email and password.'),
    # Mail scanners can open a link before the reader does, so a used token usually means the
    # account is already confirmed rather than broken.
    'already': ('🌸', 'This email address is already confirmed.',
                'Open Sakura and choose Sign in with this email and password.'),
    'invalid': ('🥀', 'That confirmation link no longer works.',
                'It has already been used or it expired. Open Sakura again and create the account a second time to get a fresh email.'),
    'absent': ('🌸', 'Sakura confirmation links land on this page.',
               'Open the button inside the email Sakura sent you, rather than this address from your history.'),
    'offline': ('🌙', 'Sakura could not reach its account service.',
                'Check your internet connection, then open the link from the email again.'),
    'foreign': ('🔒', 'Only this computer can finish a Sakura account.',
                'Open Sakura on the PC that sent the verification email.'),
}


def page(state):
    title, first, second = MESSAGES[state]
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Sakura</title><style>'
            'body{margin:0;min-height:100vh;display:grid;place-items:center;background:#14121a;'
            'color:#f4eff6;font:16px/1.6 system-ui,sans-serif;padding:24px}'
            'main{max-width:34rem;text-align:center}h1{font-size:1.35rem;margin:0 0 .6rem}'
            'p{margin:0;color:#c8bfd6}span{font-size:2rem}</style></head><body><main>'
            '<span>' + title + '</span><h1>' + first + '</h1><p>' + second + '</p></main></body></html>')


def _answer(response):
    """'already' when Auth says this token was spent, otherwise 'invalid'. Nothing is echoed."""
    try:
        detail = str(response.json().get('message') or '')
    except (ValueError, AttributeError):
        detail = ''
    return 'already' if ALREADY_USED.search(detail) else 'invalid'


def verify(token, transport=requests):
    """'confirmed', 'already', 'invalid' or 'offline' after Auth answers; the token is never echoed."""
    if not TOKEN.fullmatch(str(token or '')):
        return 'invalid'
    # A link carries a hashed token; only a typed one-time password is the literal code.
    key = 'token' if ONE_TIME_PASSWORD.fullmatch(token) else 'token_hash'
    try:
        with transport.post(CONFIRM_ENDPOINT, json={'type': 'signup', key: token},
                            headers={'apikey': SUPABASE_PUBLISHABLE_KEY},
                            timeout=(8, 25), allow_redirects=False) as response:
            return 'confirmed' if response.status_code in (200, 201) else _answer(response)
    except (requests.RequestException, ValueError, AttributeError):
        return 'offline'


def router(local_check, transport=requests):
    """local_check must be Host-only: a link clicked inside webmail is a cross-site
    navigation, so a CSRF-style guard rejects the one request this page exists to serve.
    """
    from fastapi import APIRouter, Request
    from fastapi.responses import HTMLResponse
    from starlette.concurrency import run_in_threadpool

    routes = APIRouter(prefix='/api/model-library')

    @routes.get('/confirm')
    async def confirm_link(request: Request):
        """A mail-client click is a top-level navigation, so this answers with a page, not JSON."""
        if not local_check(request):
            return HTMLResponse(page('foreign'), status_code=403, headers=HEADERS)
        token = next((value for name in PARAMS if (value := str(request.query_params.get(name) or '').strip())), '')
        state = await run_in_threadpool(verify, token, transport) if token else 'absent'
        return HTMLResponse(page(state), status_code=STATUS[state], headers=HEADERS)

    return routes
