"""Approval-aware Google Calendar access using Google's installed-app OAuth flow."""
import base64
import hashlib
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from agent_connections import secret_get, secret_set

AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
API_ROOT = 'https://www.googleapis.com/calendar/v3'
SCOPE = 'https://www.googleapis.com/auth/calendar.events.owned'
DRIVE_SCOPE = 'https://www.googleapis.com/auth/drive'


def _b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


class GoogleCalendar:
    def __init__(self):
        self.pending = None
        self.lock = threading.RLock()
        self.server = None

    def status(self):
        saved = secret_get('google-calendar')
        client_id = self._client_id(saved)
        token_client_id = saved.get('token_client_id') or saved.get('client_id')
        return {
            'configured': bool(client_id),
            'connected': bool(saved.get('refresh_token') and SCOPE in saved.get('scopes', [])
                              and token_client_id == client_id),
            'calendar': 'primary',
            'scope': SCOPE,
            'workspace_connected': bool(saved.get('refresh_token') and DRIVE_SCOPE in saved.get('scopes', []) and token_client_id == client_id),
        }

    @staticmethod
    def _client_id(saved=None):
        """Use the app's registered Google client, with saved settings for older installs."""
        saved = saved if saved is not None else secret_get('google-calendar')
        app_client_id = os.environ.get('SAKURA_GOOGLE_OAUTH_CLIENT_ID', '').strip()
        return app_client_id or str(saved.get('client_id') or '').strip()

    def configure(self, client_id, client_secret=''):
        client_id = str(client_id or '').strip()
        client_secret = str(client_secret or '').strip()
        if not client_id or len(client_id) > 500 or not client_id.endswith('.apps.googleusercontent.com'):
            raise ValueError('Enter a valid Google OAuth Desktop app client ID.')
        if len(client_secret) > 500:
            raise ValueError('The Google OAuth client secret is too long.')
        saved = secret_get('google-calendar')
        if saved.get('client_id') != client_id:
            saved = {'client_id': client_id}
        else:
            saved['client_id'] = client_id
        if client_secret:
            saved['client_secret'] = client_secret
        secret_set('google-calendar', saved)
        return self.status()

    def authorize(self, workspace=False):
        saved = secret_get('google-calendar')
        client_id = self._client_id(saved)
        if not client_id:
            raise ValueError('Google sign-in is not configured in this Sakura build yet.')
        with self.lock:
            if self.pending and time.monotonic() - self.pending['created'] <= 600:
                raise ValueError('A Google Calendar sign-in is already waiting for approval in your browser.')
            self.pending = None
        state = secrets.token_urlsafe(32)
        verifier = _b64url(secrets.token_bytes(48))
        challenge = _b64url(hashlib.sha256(verifier.encode('ascii')).digest())
        owner = self

        class Callback(BaseHTTPRequestHandler):
            def do_GET(self):
                query = parse_qs(urlparse(self.path).query)
                code = query.get('code', [''])[0]
                received_state = query.get('state', [''])[0]
                error = query.get('error', [''])[0]
                try:
                    if error:
                        owner._fail_pending(received_state)
                        message = 'Google Calendar connection was cancelled. You can close this tab and try again.'
                        status_code = 400
                    elif not code:
                        raise ValueError('Google did not return an authorization code.')
                    else:
                        owner.callback(received_state, code)
                        message = 'Google Calendar is connected. You can return to Sakura Agent.'
                        status_code = 200
                except Exception as exc:
                    message = str(exc)[:500]
                    status_code = 400
                body = ('<!doctype html><meta charset="utf-8"><title>Sakura Calendar</title>'
                        '<main style="font:16px system-ui;max-width:600px;margin:12vh auto;padding:24px;'
                        'background:#15111f;color:#f0ebf8;border:1px solid #534165;border-radius:16px">'
                        '<h2>Google Calendar</h2><p>' + _html(message) + '</p>'
                        '<p>You may close this browser tab.</p></main>').encode('utf-8')
                self.send_response(status_code)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                return

        server = HTTPServer(('127.0.0.1', 0), Callback)
        server.timeout = 0.5
        redirect_uri = f'http://127.0.0.1:{server.server_port}'
        with self.lock:
            if self.server:
                self.server.server_close()
            self.server = server
            self.pending = {'state': state, 'verifier': verifier,
                            'redirect_uri': redirect_uri, 'created': time.monotonic()}
        def wait_for_callback():
            try:
                deadline = time.monotonic() + 600
                while time.monotonic() < deadline:
                    with self.lock:
                        if not self.pending or self.pending['state'] != state:
                            break
                    server.handle_request()
            finally:
                server.server_close()
                with self.lock:
                    if self.server is server:
                        self.server = None
        threading.Thread(target=wait_for_callback, name='sakura-google-calendar-oauth', daemon=True).start()
        params = {
            'client_id': client_id, 'redirect_uri': redirect_uri,
            'response_type': 'code', 'scope': SCOPE + (' '+DRIVE_SCOPE if workspace else ''), 'state': state,
            'code_challenge': challenge, 'code_challenge_method': 'S256',
            'access_type': 'offline', 'prompt': 'select_account consent',
        }
        return AUTH_URL + '?' + urlencode(params)

    def _fail_pending(self, state):
        with self.lock:
            pending = self.pending
            if not pending or not secrets.compare_digest(str(state), pending['state']):
                raise ValueError('Google Calendar sign-in expired or state did not match. Start Connect again.')
            self.pending = None

    def callback(self, state, code):
        with self.lock:
            pending = self.pending
            if (not pending or not secrets.compare_digest(str(state), pending['state'])
                    or time.monotonic() - pending['created'] > 600):
                raise ValueError('Google Calendar sign-in expired or state did not match. Start Connect again.')
            self.pending = None
        saved = secret_get('google-calendar')
        data = {
            'client_id': self._client_id(saved), 'code': code,
            'code_verifier': pending['verifier'], 'redirect_uri': pending['redirect_uri'],
            'grant_type': 'authorization_code',
        }
        if saved.get('client_secret'):
            data['client_secret'] = saved['client_secret']
        response = requests.post(TOKEN_URL, data=data, timeout=(5, 20), allow_redirects=False)
        if response.status_code != 200:
            raise ValueError(f'Google token exchange failed (HTTP {response.status_code}). Check the OAuth client and try again.')
        value = response.json()
        granted = str(value.get('scope', '')).split()
        if not value.get('refresh_token') or SCOPE not in granted:
            raise ValueError('Google did not grant Calendar event access. Check the OAuth consent screen and requested scope.')
        saved.update(token_client_id=data['client_id'], refresh_token=value['refresh_token'], access_token=value.get('access_token', ''),
                     expires_at=time.time() + int(value.get('expires_in', 3600)), scopes=granted)
        secret_set('google-calendar', saved)
        return self.status()

    def disconnect(self):
        with self.lock:
            self.pending = None
            # The listener checks pending state at most every half second and
            # closes its own socket when it exits; avoid racing its handler.
            self.server = None
        saved=secret_get('google-calendar')
        # Disconnect this account without deleting the developer's registered
        # app configuration. A future sign-in must not need another JSON import.
        secret_set('google-calendar', {key:saved[key] for key in ('client_id','client_secret') if saved.get(key)})
        return {'ok': True}

    def config_fingerprint(self):
        saved = secret_get('google-calendar')
        return hashlib.sha256(self._client_id(saved).encode('utf-8')).hexdigest()

    def _auth(self):
        saved = secret_get('google-calendar')
        if (not saved.get('refresh_token') or SCOPE not in saved.get('scopes', [])
                or (saved.get('token_client_id') or saved.get('client_id')) != self._client_id(saved)):
            raise ValueError('Connect Google Calendar first.')
        if saved.get('expires_at', 0) <= time.time() + 30:
            data = {'client_id': self._client_id(saved), 'refresh_token': saved['refresh_token'],
                    'grant_type': 'refresh_token'}
            if saved.get('client_secret'):
                data['client_secret'] = saved['client_secret']
            response = requests.post(TOKEN_URL, data=data, timeout=(5, 20), allow_redirects=False)
            if response.status_code != 200:
                raise ValueError(f'Google Calendar token refresh failed (HTTP {response.status_code}). Reconnect the account.')
            token = response.json()
            if not token.get('access_token'):
                raise ValueError('Google did not return a Calendar access token. Reconnect the account.')
            saved.update(access_token=token['access_token'], expires_at=time.time() + int(token.get('expires_in', 3600)))
            secret_set('google-calendar', saved)
        return saved, {'Authorization': 'Bearer ' + saved['access_token']}

    def _request(self, method, path, params=None, payload=None):
        _saved, headers = self._auth()
        response = requests.request(method, API_ROOT + path, headers=headers, params=params,
                                    json=payload, timeout=(5, 20), allow_redirects=False)
        if response.status_code not in (200, 201):
            if response.status_code == 401:
                raise ValueError('Google rejected the Calendar access token. Reconnect Google Calendar.')
            raise ValueError(f'Google Calendar request failed (HTTP {response.status_code}). No write was retried.')
        return response.json() if response.content else {}

    def list_events(self, calendar_id='primary', time_min='', time_max='', query='', max_results=20):
        calendar_id = _calendar_id(calendar_id)
        params = {'maxResults': max_results, 'singleEvents': 'true', 'orderBy': 'startTime'}
        if time_min:
            params['timeMin'] = _rfc3339(time_min, 'Start of search range')
        if time_max:
            params['timeMax'] = _rfc3339(time_max, 'End of search range')
        if time_min and time_max and _instant(time_max) <= _instant(time_min):
            raise ValueError('The search end must be later than its start.')
        if query:
            params['q'] = str(query)[:200]
        result = self._request('GET', f'/calendars/{calendar_id}/events', params=params)
        return {'ok': True, 'events': [_event_summary(item) for item in result.get('items', [])[:50]],
                'calendar': result.get('summary', calendar_id)}

    def create_event(self, summary, start, end, calendar_id='primary', time_zone='', description='', location='', reminder_minutes=None):
        calendar_id = _calendar_id(calendar_id)
        start = _rfc3339(start, 'Event start')
        end = _rfc3339(end, 'Event end')
        if _instant(end) <= _instant(start):
            raise ValueError('The event end must be later than its start.')
        payload = {'summary': str(summary).strip(), 'start': {'dateTime': start}, 'end': {'dateTime': end}}
        if reminder_minutes is not None:
            if not isinstance(reminder_minutes,int) or not 0<=reminder_minutes<=40320:
                raise ValueError('Invalid notification timing.')
            payload['reminders']={'useDefault':False,'overrides':[{'method':'popup','minutes':reminder_minutes}]}
        if not payload['summary']:
            raise ValueError('Event title cannot be blank.')
        if time_zone:
            payload['start']['timeZone'] = payload['end']['timeZone'] = str(time_zone)[:100]
        if description:
            payload['description'] = str(description)[:8000]
        if location:
            payload['location'] = str(location)[:1000]
        result = self._request('POST', f'/calendars/{calendar_id}/events', payload=payload)
        return {'ok': True, 'created': True, 'event': _event_summary(result)}

    def update_event(self, event_id, calendar_id='primary', summary=None, start=None, end=None,
                     time_zone='', description=None, location=None):
        calendar_id = _calendar_id(calendar_id)
        event_id = str(event_id or '').strip()
        if not event_id or len(event_id) > 1024 or '/' in event_id:
            raise ValueError('Use the event ID returned by Google Calendar.')
        payload = {}
        if summary is not None:
            payload['summary'] = str(summary).strip()
            if not payload['summary']:
                raise ValueError('Event title cannot be blank.')
        if start is not None:
            payload['start'] = {'dateTime': _rfc3339(start, 'Event start')}
        if end is not None:
            payload['end'] = {'dateTime': _rfc3339(end, 'Event end')}
        if time_zone:
            for key in ('start', 'end'):
                if key in payload:
                    payload[key]['timeZone'] = str(time_zone)[:100]
        if ('start' in payload and 'end' in payload
                and _instant(payload['end']['dateTime']) <= _instant(payload['start']['dateTime'])):
            raise ValueError('The event end must be later than its start.')
        if description is not None:
            payload['description'] = str(description)[:8000]
        if location is not None:
            payload['location'] = str(location)[:1000]
        if not payload:
            raise ValueError('Specify at least one event field to change.')
        result = self._request('PATCH', f'/calendars/{calendar_id}/events/{event_id}', payload=payload)
        return {'ok': True, 'updated': True, 'event': _event_summary(result)}


def _calendar_id(value):
    value = str(value or 'primary').strip()
    if not value or len(value) > 500 or any(char in value for char in ('/', '?', '#', '\\')):
        raise ValueError('Enter a valid Google Calendar ID, or leave blank for primary.')
    return value


def _rfc3339(value, label):
    value = str(value or '').strip()
    # Require a time-zone suffix so event timing cannot silently depend on the PC's zone.
    import datetime
    try:
        parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError(f'{label} must be an RFC3339 date and time with a time-zone offset.') from None
    if parsed.tzinfo is None or not value.endswith(('Z', '+00:00')) and not __import__('re').search(r'[+-]\d{2}:\d{2}$', value):
        raise ValueError(f'{label} must include a time zone offset, such as +05:30.')
    return value


def _instant(value):
    import datetime
    return datetime.datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(datetime.timezone.utc)


def _event_summary(item):
    limits = {'id': 1024, 'summary': 500, 'description': 1200, 'location': 300,
              'status': 40, 'htmlLink': 1000}
    result = {key: (str(item[key])[:limits[key]] if isinstance(item[key], str) else item[key])
              for key in limits if key in item}
    result.update({key: item[key] for key in ('start', 'end') if key in item})
    return result


def _html(value):
    import html
    return html.escape(str(value), quote=True)


google_calendar = GoogleCalendar()
