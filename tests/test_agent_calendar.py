import copy
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from agent_calendar import GoogleCalendar, SCOPE, _b64url
from agent_connections import Connections
from agent_runtime import AgentRuntime


class GoogleCalendarTests(unittest.TestCase):
    def setUp(self):
        self.saved = {}
        self.calendar = GoogleCalendar()
        getter = patch('agent_calendar.secret_get', side_effect=lambda key: copy.deepcopy(self.saved.get(key, {})))
        setter = patch('agent_calendar.secret_set', side_effect=self._store)
        getter.start(); setter.start()
        self.addCleanup(getter.stop); self.addCleanup(setter.stop)
        self.calendar.configure('test.apps.googleusercontent.com')

    def _store(self, key, value):
        if value:
            self.saved[key] = copy.deepcopy(value)
        else:
            self.saved.pop(key, None)

    def test_oauth_uses_pkce_random_state_loopback_and_protected_tokens(self):
        server = Mock(); server.server_port = 49152
        with patch('agent_calendar.HTTPServer', return_value=server), patch('agent_calendar.threading.Thread.start'):
            url = self.calendar.authorize()
        query = parse_qs(urlparse(url).query)
        verifier = self.calendar.pending['verifier']
        self.assertEqual(query['redirect_uri'], ['http://127.0.0.1:49152'])
        self.assertEqual(query['scope'], [SCOPE])
        self.assertEqual(query['code_challenge_method'], ['S256'])
        self.assertEqual(query['code_challenge'], [_b64url(hashlib.sha256(verifier.encode('ascii')).digest())])
        self.assertEqual(query['prompt'], ['select_account consent'])
        self.assertNotIn('test-secret', url)
        response = Mock(status_code=200)
        response.json.return_value = {'access_token': 'short-token', 'refresh_token': 'long-token',
                                     'expires_in': 3600, 'scope': SCOPE}
        with patch('agent_calendar.requests.post', return_value=response) as exchange:
            self.assertTrue(self.calendar.callback(query['state'][0], 'one-time-code')['connected'])
            self.assertEqual(exchange.call_args.kwargs['data']['code_verifier'], verifier)
            with self.assertRaises(ValueError):
                self.calendar.callback(query['state'][0], 'one-time-code')
        self.assertNotIn('long-token', str(self.calendar.status()))
        self.assertEqual(self.saved['google-calendar']['refresh_token'], 'long-token')

    def test_app_configured_google_client_needs_no_per_user_setup(self):
        self.saved.pop('google-calendar', None)
        server = Mock(); server.server_port = 49154
        with patch.dict(os.environ, {'SAKURA_GOOGLE_OAUTH_CLIENT_ID': 'sakura.apps.googleusercontent.com'}), \
             patch('agent_calendar.HTTPServer', return_value=server), \
             patch('agent_calendar.threading.Thread.start'):
            self.assertTrue(self.calendar.status()['configured'])
            url = self.calendar.authorize()
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query['client_id'], ['sakura.apps.googleusercontent.com'])

    def test_calendar_token_is_not_reused_with_a_different_app_client(self):
        self.saved['google-calendar'].update(token_client_id='other.apps.googleusercontent.com',
                                             refresh_token='old-token', scopes=[SCOPE])
        with patch.dict(os.environ, {'SAKURA_GOOGLE_OAUTH_CLIENT_ID': 'sakura.apps.googleusercontent.com'}):
            self.assertFalse(self.calendar.status()['connected'])

    def test_sign_in_explains_when_this_build_has_no_google_client(self):
        self.saved.clear()
        self.assertFalse(self.calendar.status()['configured'])
        with self.assertRaisesRegex(ValueError, 'not configured in this Sakura build'):
            self.calendar.authorize()

    def test_disconnect_keeps_app_configuration_but_removes_account_tokens(self):
        self.saved['google-calendar'].update(client_secret='app-secret',refresh_token='account-token',access_token='short-token',scopes=[SCOPE])
        self.calendar.disconnect()
        self.assertEqual(self.saved['google-calendar'],{'client_id':'test.apps.googleusercontent.com','client_secret':'app-secret'})
        self.assertTrue(self.calendar.status()['configured'])
        self.assertFalse(self.calendar.status()['connected'])

    def test_wrong_state_never_exchanges_code(self):
        server = Mock(); server.server_port = 49153
        with patch('agent_calendar.HTTPServer', return_value=server), patch('agent_calendar.threading.Thread.start'):
            self.calendar.authorize()
        with patch('agent_calendar.requests.post') as exchange, self.assertRaises(ValueError):
            self.calendar.callback('wrong-state', 'code')
        exchange.assert_not_called()

    def test_list_events_uses_bounded_primary_calendar_query(self):
        self.saved['google-calendar'].update(refresh_token='refresh', access_token='token',
                                             expires_at=9999999999, scopes=[SCOPE])
        response = Mock(status_code=200, content=b'{}')
        response.json.return_value = {'summary': 'My calendar', 'items': [{'id': 'evt1', 'summary': 'Meeting'}]}
        with patch('agent_calendar.requests.request', return_value=response) as request:
            result = self.calendar.list_events(time_min='2026-10-22T00:00:00+05:30',
                                               time_max='2026-10-23T00:00:00+05:30', max_results=10)
        self.assertEqual(result['events'][0]['id'], 'evt1')
        self.assertEqual(request.call_args.args[:2], ('GET', 'https://www.googleapis.com/calendar/v3/calendars/primary/events'))
        self.assertEqual(request.call_args.kwargs['params']['maxResults'], 10)

    def test_event_time_requires_timezone_and_valid_range(self):
        with self.assertRaisesRegex(ValueError, 'time zone'):
            self.calendar.create_event('Meeting', '2026-10-22T10:00:00', '2026-10-22T11:00:00')
        with self.assertRaisesRegex(ValueError, 'later'):
            self.calendar.create_event('Meeting', '2026-10-22T11:00:00+05:30', '2026-10-22T10:00:00+05:30')


class CalendarApprovalTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root = Path(self.folder.name)
        self.runtime = AgentRuntime(Connections(root / 'connections.json'), store_path=root / 'history.json')
        self.run = self.runtime.new_run('Schedule a meeting', self.folder.name)

    def test_calendar_write_waits_for_exact_one_shot_approval(self):
        with patch('agent_calendar.google_calendar.status', return_value={'connected': True}), \
             patch('agent_calendar.google_calendar.config_fingerprint', return_value='config-a'), \
             patch('agent_calendar.google_calendar.create_event', return_value={'ok': True, 'created': True}) as create:
            proposal = self.runtime.propose(self.run['id'], 'calendar.events.create', {
                'summary': 'Design review', 'start': '2026-10-23T15:00:00+05:30',
                'end': '2026-10-23T16:00:00+05:30'})['steps'][-1]
            create.assert_not_called()
            self.assertEqual(proposal['preview']['operation'], 'Create calendar event')
            result = self.runtime.decide(proposal['id'], False)
            create.assert_not_called()
            self.assertEqual(result['action']['status'], 'rejected')

            proposal = self.runtime.propose(self.run['id'], 'calendar.events.create', {
                'summary': 'Design review', 'start': '2026-10-23T15:00:00+05:30',
                'end': '2026-10-23T16:00:00+05:30'})['steps'][-1]
            self.runtime.decide(proposal['id'], True)
            create.assert_called_once()

    def test_a_different_google_account_invalidates_a_pending_calendar_write(self):
        """The OAuth client id is identical for two accounts, so it cannot guard a write."""
        accounts = iter([{'refresh_token': 'account-one', 'scopes': ['calendar']},
                         {'refresh_token': 'account-two', 'scopes': ['calendar']}])
        with patch('agent_calendar.google_calendar.status', return_value={'connected': True}), \
             patch('agent_calendar.google_calendar.config_fingerprint', return_value='same-client-id'), \
             patch('agent_google.secret_get', side_effect=lambda name: next(accounts)), \
             patch('agent_calendar.google_calendar.create_event') as create:
            proposal = self.runtime.propose(self.run['id'], 'calendar.events.create', {
                'summary': 'Design review', 'start': '2026-10-23T15:00:00+05:30',
                'end': '2026-10-23T16:00:00+05:30'})['steps'][-1]
            result = self.runtime.decide(proposal['id'], True)
        create.assert_not_called()
        self.assertEqual(result['action']['status'], 'failed')
        self.assertIn('connection changed', result['action']['result']['error'])

    def test_changed_calendar_connection_invalidates_pending_approval(self):
        with patch('agent_calendar.google_calendar.status', return_value={'connected': True}), \
             patch('agent_calendar.google_calendar.config_fingerprint', side_effect=['config-a', 'config-b']), \
             patch('agent_calendar.google_calendar.create_event') as create:
            proposal = self.runtime.propose(self.run['id'], 'calendar.events.create', {
                'summary': 'Design review', 'start': '2026-10-23T15:00:00+05:30',
                'end': '2026-10-23T16:00:00+05:30'})['steps'][-1]
            result = self.runtime.decide(proposal['id'], True)
        create.assert_not_called()
        self.assertEqual(result['action']['status'], 'failed')
        self.assertIn('connection changed', result['action']['result']['error'])


if __name__ == '__main__':
    unittest.main()
