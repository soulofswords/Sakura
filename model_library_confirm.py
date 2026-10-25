"""Spend the tokens in Sakura's emailed links when the user clicks them in their mailbox.

Sakura is a desktop app, so the links Supabase embeds in its emails have nowhere to land:
a confirmation hash must be posted back to Auth before the account becomes usable, and a
recovery hash must be exchanged for the short-lived session that carries the new password.
"""
import re
import secrets
import threading
import time
from urllib.parse import parse_qs

import requests

from model_library_config import SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY

PARAMS = ('confirmation_token', 'verification_token', 'token', 'otp')
RECOVERY_PARAMS = ('recovery_token', 'token', 'otp')
TOKEN = re.compile(r'^[A-Za-z0-9_-]{6,512}$')
ONE_TIME_PASSWORD = re.compile(r'^\d{4,10}$')
SLOT = re.compile(r'^[A-Za-z0-9_-]{24,64}$')
ALREADY_USED = re.compile(r'\balready\b', re.I)
WEAK_PASSWORD = re.compile(r'weak|length|character', re.I)
CONFIRM_ENDPOINT = SUPABASE_URL + '/auth/v1/verify'
USER_ENDPOINT = SUPABASE_URL + '/auth/v1/user'
RESET_TTL = 600
MAX_PENDING = 8
MAX_BODY = 65536
HEADERS = {'Cache-Control': 'no-store', 'X-Frame-Options': 'SAMEORIGIN',
           'Referrer-Policy': 'no-referrer', 'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'"}
# The reset page posts a form back to this server, so it needs form-action on top of the
# lock-down the confirmation page gets.
FORM_HEADERS = {**HEADERS, 'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'"}
# Visiting a page without a token is normal history noise, not an error; only a spent or
# unreachable confirmation answers with a failure status.
STATUS = {'confirmed': 200, 'already': 200, 'absent': 200, 'invalid': 400, 'offline': 503, 'foreign': 403,
          'form': 200, 'done': 200, 'length': 400, 'mismatch': 400, 'weak': 400, 'expired': 400, 'failed': 400}
# States that still owe the user a working form, so the slot id goes back into it.
RETRYABLE = ('form', 'length', 'mismatch', 'weak', 'offline')

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

RESET_MESSAGES = {
    'form': ('🔑', 'Choose a new password.',
             'This link was verified, so Sakura only needs the new password. It works once.'),
    'done': ('🌸', 'Your password is changed.',
             'Open Sakura and choose Sign in with your new password.'),
    'length': ('🥀', 'That password is the wrong length.',
               'Sakura accounts need 8 to 256 characters.'),
    'mismatch': ('🥀', 'The two passwords do not match.',
                 'Type the new password the same way twice.'),
    'weak': ('🥀', 'That password is not strong enough.',
             'Mix letters, numbers and a symbol, then try again.'),
    'expired': ('🥀', 'That reset link has already been used or has gone stale.',
                'Choose Forgot password in Sakura to get a fresh link.'),
    'failed': ('🥀', 'Sakura could not set that password.',
               'Choose Forgot password in Sakura to get a fresh link, then try again.'),
    'invalid': ('🥀', 'That reset link no longer works.',
                'It has already been used or it expired. Choose Forgot password in Sakura to get a fresh one.'),
    'already': ('🌸', 'That reset link has already been used.',
                'If you set a new password already, sign in with it. Otherwise choose Forgot password in Sakura again.'),
    'absent': ('🌸', 'Sakura reset links land on this page.',
               'Open the button inside the reset email rather than this address from your history.'),
    'offline': ('🌙', 'Sakura could not reach its account service.',
                'Check your internet connection, then open the link from the email again.'),
    'foreign': ('🔒', 'Only this computer can finish a Sakura account.',
                'Open Sakura on the PC that sent the reset email.'),
}

FIELD = ('style="display:block;width:100%;box-sizing:border-box;margin-top:.35rem;padding:.6rem;'
         'background:#1e1a26;color:#f4eff6;border:1px solid #4a4157;border-radius:8px"')
FIELD_REVEAL = FIELD.replace('border-radius:8px"', 'border-radius:8px;padding-right:2.5rem"')
EYE = ('<button type="button" data-reveal="{target}" aria-pressed="false" aria-label="Show password" '
       'title="Show password" style="position:absolute;right:2px;top:50%;transform:translateY(-50%);'
       'border:0;background:transparent;cursor:pointer;font-size:1.05rem;line-height:1">👁</button>')


def _reveal_script(nonce):
    """The only script a reset page can run, because its CSP allows just this response's nonce.

    It flips the two password fields between hidden and plain text; nothing else needs to execute
    here, and the slot id is already regex-checked, so no page data is readable from the script.
    """
    return ('<script nonce="' + nonce + '">document.querySelectorAll("[data-reveal]").forEach(function (button) {'
            'button.onclick = function () {var field = document.getElementById(button.dataset.reveal);'
            'var hidden = field.type === "password"; field.type = hidden ? "text" : "password";'
            'button.setAttribute("aria-pressed", String(hidden));'
            'button.setAttribute("aria-label", (hidden ? "Hide" : "Show") + " password");'
            'button.title = button.getAttribute("aria-label");};});</script>')


def _field(label, name, identifier, bottom='.9rem'):
    return ('<label style="display:block;margin:0 0 ' + bottom + '">' + label
            + '<span style="display:block;position:relative">'
            '<input id="' + identifier + '" name="' + name + '" type="password" minlength="8" maxlength="256" required '
            'autocomplete="new-password" ' + FIELD_REVEAL + '>' + EYE.replace('{target}', identifier) + '</span></label>')


def _form(identifier, nonce=''):
    # The id comes from secrets.token_urlsafe and is re-checked against SLOT, so it needs no escaping.
    return ('<form method="post" action="/api/model-library/reset" autocomplete="off" style="margin-top:1.4rem;text-align:left">'
            '<input name="reset_id" type="hidden" value="' + identifier + '">'
            + _field('New password', 'password', 'sakura-new-password')
            + _field('Repeat it', 'confirm', 'sakura-new-password-repeat', '1.2rem')
            + '<button type="submit" style="padding:.6rem 1.1rem;border:0;border-radius:8px;background:#7c5cff;color:#fff;font:inherit">'
            'Set new password</button></form>' + (_reveal_script(nonce) if nonce else ''))


def _shell(title, first, second, body=''):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Sakura</title><style>'
            'body{margin:0;min-height:100vh;display:grid;place-items:center;background:#14121a;'
            'color:#f4eff6;font:16px/1.6 system-ui,sans-serif;padding:24px}'
            'main{max-width:34rem;text-align:center}h1{font-size:1.35rem;margin:0 0 .6rem}'
            'p{margin:0;color:#c8bfd6}span{font-size:2rem}</style></head><body><main>'
            '<span>' + title + '</span><h1>' + first + '</h1><p>' + second + '</p>' + body + '</main></body></html>')


def page(state):
    return _shell(*MESSAGES[state])


def reset_page(state, identifier='', nonce=''):
    """The new-password form on the states that can still use it, a plain message on the rest."""
    title, first, second = RESET_MESSAGES[state]
    return _shell(title, first, second, _form(identifier, nonce) if state in RETRYABLE and identifier else '')


def _detail(response):
    """The provider's own safe hints about a failure.

    Auth fills in a different field depending on the endpoint and its version, and only
    joining them lets "already used" be recognised wherever it is actually written.
    """
    try:
        data = response.json()
    except (ValueError, AttributeError):
        return ''
    if not isinstance(data, dict):
        return ''
    return ' '.join(str(data.get(key) or '') for key in
                    ('error_code', 'code', 'msg', 'message', 'error_description'))


def _spend(token, kind, transport):
    """(state, access_token, email) after Auth answers a link token; the token never comes back."""
    if not TOKEN.fullmatch(str(token or '')):
        return 'invalid', '', ''
    # A link carries a hashed token; only a typed one-time password is the literal code.
    key = 'token' if ONE_TIME_PASSWORD.fullmatch(token) else 'token_hash'
    try:
        with transport.post(CONFIRM_ENDPOINT, json={'type': kind, key: token},
                            headers={'apikey': SUPABASE_PUBLISHABLE_KEY},
                            timeout=(8, 25), allow_redirects=False) as response:
            if response.status_code in (200, 201):
                try:
                    data = response.json() or {}
                except ValueError:
                    data = {}
                session = str(data.get('access_token') or '')
                email = str((data.get('user') or {}).get('email') or '')
                return 'ok', session, email
            return ('already' if ALREADY_USED.search(_detail(response)) else 'invalid'), '', ''
    except (requests.RequestException, ValueError, AttributeError):
        return 'offline', '', ''


def verify(token, transport=requests):
    """'confirmed', 'already', 'invalid' or 'offline'. Nothing the provider said is echoed."""
    state, _, _ = _spend(token, 'signup', transport)
    return 'confirmed' if state == 'ok' else state


def recover(token, transport=requests):
    """('recovered', session, email) when the reset link is live, else ('invalid'|'already'|'offline', '', '')."""
    state, session, email = _spend(token, 'recovery', transport)
    if state != 'ok':
        return state, '', ''
    # A recovery answer without a session cannot carry a new password, so treat it as a failure
    # rather than offering a form that is guaranteed to reject it.
    return ('recovered', session, email) if session else ('invalid', '', '')


def set_password(session, password, email='', transport=requests):
    """'done', 'weak', 'failed' or 'offline' after Auth answers a new password."""
    try:
        with transport.put(USER_ENDPOINT, json={'password': password},
                           headers={'apikey': SUPABASE_PUBLISHABLE_KEY, 'Authorization': 'Bearer ' + session},
                           timeout=(8, 25), allow_redirects=False) as response:
            if response.status_code != 200:
                detail = _detail(response)
                return 'weak' if WEAK_PASSWORD.search(detail) else 'failed'
            # A 200 that is not this account proves nothing about the password, so only the
            # updated user object may say it changed.
            try:
                data = response.json()
            except ValueError:
                return 'failed'
            if not isinstance(data, dict) or not data.get('id'):
                return 'failed'
            if email and str(data.get('email') or '').casefold() != email.casefold():
                return 'failed'
            return 'done'
    except (requests.RequestException, ValueError, AttributeError):
        return 'offline'


def _retire():
    now = time.time()
    for stale in [key for key, (_, until, _) in _pending.items() if until < now]:
        _pending.pop(stale, None)


def hold(session, email=''):
    """Hand out a one-use id for a recovered session; the session itself never reaches the page."""
    identifier = secrets.token_urlsafe(18)
    with _pending_lock:
        _retire()
        while len(_pending) >= MAX_PENDING:
            _pending.pop(next(iter(_pending)))
        _pending[identifier] = (session, time.time() + RESET_TTL, email)
    return identifier


def take(identifier):
    """Pop a slot, returning (session, deadline, email); an unknown or spent id yields ('', 0, '')."""
    with _pending_lock:
        _retire()
        return _pending.pop(str(identifier or ''), ('', 0, ''))


def give_back(identifier, session, until, email=''):
    """Return a slot the user has not yet spent, so a typo does not cost them a new email."""
    if not session or until <= time.time():
        return
    with _pending_lock:
        while len(_pending) >= MAX_PENDING:
            _pending.pop(next(iter(_pending)))
        _pending[str(identifier)] = (session, until, email)


def reset_pending(email):
    """True while a verified reset link waits unspent for this address, so the sign-in error can
    say that the new password is not live yet rather than calling it a wrong password."""
    target = str(email or '').casefold()
    if not target:
        return False
    with _pending_lock:
        _retire()
        return any(kept.casefold() == target for _, _, kept in _pending.values())


_pending = {}
_pending_lock = threading.Lock()


def router(local_check, form_check, transport=requests):
    """local_check must be Host-only: a link clicked inside webmail is a cross-site
    navigation, so a CSRF-style guard rejects the one request these pages exist to serve.

    form_check is the stricter guard. It only ever sees the request this page's own form
    makes, and that is a same-origin submit, so protecting the reset endpoint does not
    break the flow it protects.
    """
    from fastapi import APIRouter, Request
    from fastapi.responses import HTMLResponse
    from starlette.concurrency import run_in_threadpool

    routes = APIRouter(prefix='/api/model-library')

    def argument(request, names):
        return next((value for name in names if (value := str(request.query_params.get(name) or '').strip())), '')

    def html(state, identifier='', code=None, headers=HEADERS):
        # A page that can still take a password also carries the reveal script, and that script is
        # allowed only for this response, because the CSP names a nonce generated here.
        nonce = secrets.token_urlsafe(18) if identifier else ''
        if nonce:
            headers = {**headers, 'Content-Security-Policy': headers['Content-Security-Policy']
                       + "; script-src 'nonce-" + nonce + "'"}
        return HTMLResponse(reset_page(state, identifier, nonce),
                            status_code=STATUS[state] if code is None else code, headers=headers)

    @routes.get('/confirm')
    async def confirm_link(request: Request):
        """A mail-client click is a top-level navigation, so this answers with a page, not JSON."""
        if not local_check(request):
            return HTMLResponse(page('foreign'), status_code=403, headers=HEADERS)
        token = argument(request, PARAMS)
        state = await run_in_threadpool(verify, token, transport) if token else 'absent'
        return HTMLResponse(page(state), status_code=STATUS[state], headers=HEADERS)

    @routes.get('/reset')
    async def reset_link(request: Request):
        """A live recovery link becomes a form whose session stays in this process's memory."""
        if not local_check(request):
            return html('foreign', code=403)
        token = argument(request, RECOVERY_PARAMS)
        if not token:
            return html('absent')
        state, session, email = await run_in_threadpool(recover, token, transport)
        if state != 'recovered':
            return html(state)
        return html('form', hold(session, email), headers=FORM_HEADERS)

    @routes.post('/reset')
    async def apply_reset(request: Request):
        """Auth only ever hears a new password from a form this page handed out."""
        if not form_check(request):
            return html('foreign', code=403, headers=FORM_HEADERS)
        # A form encoded body needs no multipart parser, and the cap keeps a junk POST cheap.
        fields = parse_qs((await request.body())[:MAX_BODY].decode('utf-8', 'replace'), keep_blank_values=True)

        def value(name):
            return str((fields.get(name) or [''])[0])

        identifier = value('reset_id')
        if not SLOT.fullmatch(identifier):
            return html('expired', headers=FORM_HEADERS)
        session, until, email = take(identifier)
        if not session:
            return html('expired', headers=FORM_HEADERS)
        password = value('password')
        if not 8 <= len(password) <= 256:
            state = 'length'
        elif password != value('confirm'):
            state = 'mismatch'
        else:
            state = await run_in_threadpool(set_password, session, password, email, transport)
        if state in RETRYABLE:
            give_back(identifier, session, until, email)
            return html(state, identifier, headers=FORM_HEADERS)
        return html(state, headers=FORM_HEADERS)

    return routes
