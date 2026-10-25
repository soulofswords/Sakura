import re
import time
import unittest
from unittest.mock import patch

import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient

import model_library_confirm
from model_library_confirm import CONFIRM_ENDPOINT, USER_ENDPOINT, router, verify
from model_library_config import SUPABASE_PUBLISHABLE_KEY

HASH = 'sF4d2sG7hJ0kL9pQrT3vW6xZ1cB5nM8a'
CODE = '123456'
SESSION = 'sess-' + 'x' * 40
FIELD = re.compile(r'name="reset_id" type="hidden" value="([^"]+)"')


class Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = payload if payload is not None else {'session': {'access_token': SESSION}}
        self.closed = False

    def json(self):
        return self.payload

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def recovered():
    """What Auth answers a live recovery link with: a session, not just a user."""
    return Response(200, {'access_token': SESSION, 'refresh_token': 'refresh-' + 'y' * 24,
                          'user': {'id': 'u1', 'email': 'tester@example.com'}})


def updated(email='tester@example.com'):
    """What Auth answers a successful PUT /user with: the updated account itself."""
    return Response(200, {'id': 'u1', 'aud': 'authenticated', 'email': email})


class Transport:
    def __init__(self, reply=None, error=None, put_reply=None):
        self.calls = []
        self.reply = reply if reply is not None else Response()
        self.put_reply = put_reply
        self.error = error

    def _send(self, method, url, json, headers, timeout, allow_redirects):
        self.calls.append({'method': method, 'url': url, 'json': json, 'headers': headers,
                           'timeout': timeout, 'allow_redirects': allow_redirects})
        if self.error:
            raise self.error
        if method == 'PUT':
            # Auth answers a successful password change with the updated user, and nothing else.
            return self.put_reply if self.put_reply is not None else updated()
        return self.reply

    def post(self, url, json=None, headers=None, timeout=None, allow_redirects=None):
        return self._send('POST', url, json, headers, timeout, allow_redirects)

    def put(self, url, json=None, headers=None, timeout=None, allow_redirects=None):
        return self._send('PUT', url, json, headers, timeout, allow_redirects)


def client(local=True, form_local=True, transport=None):
    app = FastAPI()
    app.include_router(router(lambda request: local, lambda request: form_local,
                              transport=transport or Transport()))
    return TestClient(app)


class Verify(unittest.TestCase):
    def test_link_token_is_posted_as_a_hash_with_the_publishable_key(self):
        transport = Transport()
        self.assertEqual(verify(HASH, transport), 'confirmed')
        call = transport.calls[0]
        self.assertEqual(call['url'], CONFIRM_ENDPOINT)
        self.assertEqual(call['json'], {'type': 'signup', 'token_hash': HASH})
        self.assertEqual(call['headers'], {'apikey': SUPABASE_PUBLISHABLE_KEY})
        self.assertFalse(call['allow_redirects'])

    def test_a_typed_one_time_password_is_sent_as_the_code_itself(self):
        transport = Transport()
        self.assertEqual(verify(CODE, transport), 'confirmed')
        self.assertEqual(transport.calls[0]['json'], {'type': 'signup', 'token': CODE})

    def test_auth_rejection_is_reported_instead_of_confirmation(self):
        for status in (400, 401, 422, 429):
            with self.subTest(status=status):
                self.assertEqual(verify(HASH, Transport(reply=Response(status))), 'invalid')

    def test_a_token_a_scanner_already_opened_reads_as_confirmed_not_broken(self):
        spent = Response(400, {'code': 'bad_request', 'message': 'Token has already been used once, please use a new confirmation link'})
        self.assertEqual(verify(HASH, Transport(reply=spent)), 'already')

    def test_auth_writes_its_reason_in_whichever_field_it_prefers(self):
        # Supabase's GoTrue bodies use msg, while its docs and other endpoints use message.
        for field in ('msg', 'message', 'error_description'):
            with self.subTest(field=field):
                spent = Response(400, {'code': 400, 'error_code': 'bad_request',
                                       field: 'Token has already been used once'})
                self.assertEqual(verify(HASH, Transport(reply=spent)), 'already')

    def test_an_unreadable_error_body_stays_invalid(self):
        class Broken(Response):
            def json(self):
                raise ValueError('not json')

        self.assertEqual(verify(HASH, Transport(reply=Broken(422))), 'invalid')

    def test_an_unreachable_service_is_offline_and_never_claims_success(self):
        self.assertEqual(verify(HASH, Transport(error=requests.ConnectionError())), 'offline')
        self.assertEqual(verify(HASH, Transport(error=requests.Timeout())), 'offline')

    def test_a_malformed_token_never_reaches_the_network(self):
        for value in ('', 'short', HASH + '!' * 8, 'a' * 513, 'has space', None):
            with self.subTest(value=value):
                transport = Transport()
                self.assertEqual(verify(value, transport), 'invalid')
                self.assertEqual(transport.calls, [])

    def test_the_response_is_always_closed(self):
        reply = Response()
        verify(HASH, Transport(reply=reply))
        self.assertTrue(reply.closed)


class Route(unittest.TestCase):
    def test_a_link_with_a_good_token_confirms_in_the_users_own_words(self):
        transport = Transport()
        response = client(transport=transport).get('/api/model-library/confirm?confirmation_token=' + HASH)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Your email address is confirmed.', response.text)
        self.assertEqual(transport.calls[0]['json']['token_hash'], HASH)

    def test_every_supported_parameter_name_is_recognised(self):
        for name in ('confirmation_token', 'verification_token', 'token', 'otp'):
            with self.subTest(name=name):
                transport = Transport()
                response = client(transport=transport).get('/api/model-library/confirm?' + name + '=' + HASH)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(transport.calls), 1)
                self.assertEqual(transport.calls[0]['json']['token_hash'], HASH)

    def test_an_opened_page_without_a_token_is_help_instead_of_an_error(self):
        transport = Transport()
        response = client(transport=transport).get('/api/model-library/confirm')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Open the button inside the email', response.text)
        self.assertEqual(transport.calls, [])

    def test_a_spent_token_and_a_dead_service_get_honest_statuses(self):
        self.assertEqual(client(transport=Transport(reply=Response(422))).get(
            '/api/model-library/confirm?confirmation_token=' + HASH).status_code, 400)
        self.assertEqual(client(transport=Transport(error=requests.ConnectionError())).get(
            '/api/model-library/confirm?confirmation_token=' + HASH).status_code, 503)

    def test_a_link_a_scanner_opened_first_still_ends_with_a_working_account(self):
        spent = Response(400, {'message': 'Token has already been used once'})
        response = client(transport=Transport(reply=spent)).get(
            '/api/model-library/confirm?confirmation_token=' + HASH)
        self.assertEqual(response.status_code, 200)
        self.assertIn('already confirmed', response.text)
        self.assertNotIn('create the account a second time', response.text)

    def test_the_token_and_the_signed_in_session_stay_out_of_the_page(self):
        response = client(transport=Transport()).get('/api/model-library/confirm?confirmation_token=' + HASH)
        self.assertNotIn(HASH, response.text)
        self.assertNotIn('access_token', response.text)
        self.assertNotIn('sess-', response.text)

    def test_a_page_not_served_on_this_computer_cannot_spend_a_token(self):
        transport = Transport()
        response = client(local=False, transport=transport).get('/api/model-library/confirm?confirmation_token=' + HASH)
        self.assertEqual(response.status_code, 403)
        self.assertIn('Only this computer', response.text)
        self.assertEqual(transport.calls, [])

    def test_the_page_refuses_frames_referrers_and_caching(self):
        response = client().get('/api/model-library/confirm')
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(response.headers['x-frame-options'], 'SAMEORIGIN')
        self.assertEqual(response.headers['referrer-policy'], 'no-referrer')
        self.assertIn("default-src 'none'", response.headers['content-security-policy'])

    def test_the_library_owner_cannot_leave_the_page_without_a_message(self):
        for state in ('confirmed', 'already', 'invalid', 'absent', 'offline', 'foreign'):
            with self.subTest(state=state):
                page = model_library_confirm.page(state)
                self.assertIn('<title>Sakura</title>', page)
                self.assertGreater(len(page), 400)
        for state in model_library_confirm.MESSAGES:
            self.assertIn(state, model_library_confirm.STATUS)
        with self.assertRaises(KeyError):
            model_library_confirm.page('maybe')

    def test_every_reset_state_has_a_page_and_a_status(self):
        for state in model_library_confirm.RESET_MESSAGES:
            with self.subTest(state=state):
                page = model_library_confirm.reset_page(state)
                self.assertIn('<title>Sakura</title>', page)
                self.assertIn(state, model_library_confirm.STATUS)
        with self.assertRaises(KeyError):
            model_library_confirm.reset_page('maybe')

    def test_only_a_state_that_owes_a_retry_shows_the_form(self):
        for state in model_library_confirm.RETRYABLE:
            with self.subTest(state=state):
                self.assertIn('name="password"', model_library_confirm.reset_page(state, 'x' * 24))
        for state in set(model_library_confirm.RESET_MESSAGES) - set(model_library_confirm.RETRYABLE):
            with self.subTest(state=state):
                self.assertNotIn('<form', model_library_confirm.reset_page(state, 'x' * 24))


def open_form(transport=None, **guard):
    """Follow a real reset link far enough to hand back the client and the slot id on the page."""
    probe = client(transport=transport or Transport(reply=recovered()), **guard)
    page = probe.get('/api/model-library/reset?recovery_token=' + HASH)
    return probe, page


class Recover(unittest.TestCase):
    def test_a_recovery_link_is_spent_as_a_recovery_type_hash(self):
        transport = Transport(reply=recovered())
        _, page = open_form(transport)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(transport.calls[0]['url'], CONFIRM_ENDPOINT)
        self.assertEqual(transport.calls[0]['json'], {'type': 'recovery', 'token_hash': HASH})

    def test_a_typed_recovery_code_is_sent_as_the_code_itself(self):
        transport = Transport(reply=recovered())
        client(transport=transport).get('/api/model-library/reset?token=' + CODE)
        self.assertEqual(transport.calls[0]['json'], {'type': 'recovery', 'token': CODE})

    def test_a_live_link_becomes_a_password_form(self):
        page = client(transport=Transport(reply=recovered())).get(
            '/api/model-library/reset?recovery_token=' + HASH)
        self.assertEqual(page.status_code, 200)
        self.assertIn('Choose a new password.', page.text)
        self.assertIn('action="/api/model-library/reset"', page.text)
        self.assertIn('method="post"', page.text)
        self.assertIn('name="password"', page.text)

    def test_the_session_and_the_token_stay_out_of_the_page(self):
        page = client(transport=Transport(reply=recovered())).get(
            '/api/model-library/reset?recovery_token=' + HASH)
        self.assertNotIn(SESSION, page.text)
        self.assertNotIn(HASH, page.text)
        self.assertNotIn('access_token', page.text)

    def test_the_form_page_is_allowed_to_post_only_back_to_itself(self):
        page = client(transport=Transport(reply=recovered())).get(
            '/api/model-library/reset?recovery_token=' + HASH)
        self.assertIn("form-action 'self'", page.headers['content-security-policy'])
        self.assertEqual(page.headers['cache-control'], 'no-store')

    def test_the_reveal_script_is_allowed_only_for_the_response_that_carries_it(self):
        def nonce(response):
            found = re.search(r"script-src 'nonce-([^']+)'", response.headers['content-security-policy'])
            return found.group(1) if found else ''

        def form():
            return client(transport=Transport(reply=recovered())).get(
                '/api/model-library/reset?recovery_token=' + HASH)

        first, second = form(), form()
        self.assertEqual(first.text.count('data-reveal='), 2, 'Both password fields get an eye.')
        self.assertIn('<script nonce="' + nonce(first) + '">', first.text)
        self.assertTrue(nonce(first))
        self.assertNotEqual(nonce(first), nonce(second), 'A nonce may not be reused across responses.')
        plain = client(transport=Transport()).get('/api/model-library/reset?recovery_token=' + HASH)
        self.assertNotIn('<form', plain.text)
        self.assertEqual(nonce(plain), '', 'A page without the form runs no script at all.')

    def test_a_link_that_carries_no_session_offers_no_form(self):
        transport = Transport()
        page = client(transport=transport).get('/api/model-library/reset?recovery_token=' + HASH)
        self.assertEqual(page.status_code, 400)
        self.assertIn('reset link no longer works', page.text)
        self.assertNotIn('<form', page.text)

    def test_an_opened_link_remembers_which_address_it_was_for(self):
        model_library_confirm._pending.clear()
        self.addCleanup(model_library_confirm._pending.clear)
        client(transport=Transport(reply=recovered())).get('/api/model-library/reset?recovery_token=' + HASH)
        self.assertTrue(model_library_confirm.reset_pending('tester@example.com'))

    def test_a_link_a_scanner_opened_first_is_reported_as_used_not_broken(self):
        spent = Transport(reply=Response(400, {'message': 'Token has already been used once'}))
        page = client(transport=spent).get('/api/model-library/reset?recovery_token=' + HASH)
        self.assertEqual(page.status_code, 200)
        self.assertIn('already been used', page.text)
        self.assertNotIn('<form', page.text)

    def test_a_dead_service_and_an_empty_page_keep_their_honest_statuses(self):
        self.assertEqual(client(transport=Transport(error=requests.ConnectionError())).get(
            '/api/model-library/reset?recovery_token=' + HASH).status_code, 503)
        transport = Transport()
        page = client(transport=transport).get('/api/model-library/reset')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Open the button inside the reset email', page.text)
        self.assertEqual(transport.calls, [])

    def test_a_link_opened_on_another_machine_cannot_even_show_the_form(self):
        transport = Transport()
        page = client(local=False, transport=transport).get('/api/model-library/reset?recovery_token=' + HASH)
        self.assertEqual(page.status_code, 403)
        self.assertNotIn('<form', page.text)
        self.assertEqual(transport.calls, [])


class Reset(unittest.TestCase):
    def submit(self, probe, identifier, password='FreshPassw0rd!', confirm=None):
        return probe.post('/api/model-library/reset', data={
            'reset_id': identifier, 'password': password,
            'confirm': password if confirm is None else confirm})

    def put_calls(self, transport):
        return [call for call in transport.calls if call['method'] == 'PUT']

    def test_the_new_password_reaches_auth_with_the_recovered_session(self):
        transport = Transport(reply=recovered())
        probe, page = open_form(transport)
        response = self.submit(probe, FIELD.search(page.text).group(1))
        self.assertEqual(response.status_code, 200)
        self.assertIn('Your password is changed.', response.text)
        self.assertNotIn('FreshPassw0rd!', response.text)
        self.assertEqual(len(self.put_calls(transport)), 1)
        self.assertEqual(self.put_calls(transport)[0]['url'], USER_ENDPOINT)
        self.assertEqual(self.put_calls(transport)[0]['json'], {'password': 'FreshPassw0rd!'})
        self.assertEqual(self.put_calls(transport)[0]['headers'], {'apikey': SUPABASE_PUBLISHABLE_KEY,
                                                                  'Authorization': 'Bearer ' + SESSION})

    def test_a_short_or_mismatched_password_never_reaches_auth(self):
        for case in ({'password': 'abc'}, {'password': 'FreshPassw0rd!', 'confirm': 'FreshPassw00d!'}):
            with self.subTest(**case):
                transport = Transport(reply=recovered())
                probe, page = open_form(transport)
                response = self.submit(probe, FIELD.search(page.text).group(1), **case)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.put_calls(transport), [])

    def test_a_rejected_password_leaves_the_link_usable_for_one_more_try(self):
        transport = Transport(reply=recovered(), put_reply=Response(422, {'error_code': 'weak_password'}))
        probe, page = open_form(transport)
        identifier = FIELD.search(page.text).group(1)
        first = self.submit(probe, identifier)
        self.assertEqual(first.status_code, 400)
        self.assertIn('not strong enough', first.text)
        self.assertIn('name="password"', first.text)
        self.submit(probe, identifier)
        self.assertEqual(len(self.put_calls(transport)), 2)

    def test_the_link_sets_a_password_once(self):
        transport = Transport(reply=recovered())
        probe, page = open_form(transport)
        identifier = FIELD.search(page.text).group(1)
        self.assertEqual(self.submit(probe, identifier).status_code, 200)
        again = self.submit(probe, identifier)
        self.assertEqual(again.status_code, 400)
        self.assertIn('already been used or has gone stale', again.text)
        self.assertEqual(len(self.put_calls(transport)), 1)

    def test_a_made_up_slot_is_expired_before_the_network(self):
        for identifier in ('', 'short', 'x' * 200, SESSION):
            with self.subTest(identifier=identifier):
                transport = Transport(reply=recovered())
                probe, page = open_form(transport)
                response = self.submit(probe, identifier)
                self.assertEqual(response.status_code, 400)
                self.assertIn('already been used or has gone stale', response.text)
                self.assertEqual(self.put_calls(transport), [])

    def test_an_unreachable_service_says_so_and_keeps_the_slot(self):
        transport = Transport(reply=recovered())
        probe, page = open_form(transport)
        identifier = FIELD.search(page.text).group(1)
        transport.error = requests.ConnectionError()
        response = self.submit(probe, identifier)
        self.assertEqual(response.status_code, 503)
        self.assertIn('could not reach its account service', response.text)
        transport.error = None
        self.submit(probe, identifier)
        self.assertEqual(len(self.put_calls(transport)), 2)

    def test_a_form_driven_by_another_website_cannot_change_a_password(self):
        transport = Transport(reply=recovered())
        probe, page = open_form(transport, form_local=False)
        response = self.submit(probe, FIELD.search(page.text).group(1))
        self.assertEqual(response.status_code, 403)
        self.assertIn('Only this computer', response.text)
        self.assertEqual(self.put_calls(transport), [])


class SetPassword(unittest.TestCase):
    def test_the_new_password_is_put_with_the_recovered_bearer_session(self):
        transport = Transport(put_reply=Response(200, {'id': 'u1'}))
        self.assertEqual(model_library_confirm.set_password(SESSION, 'FreshPassw0rd!', transport=transport), 'done')
        call = transport.calls[0]
        self.assertEqual((call['method'], call['url']), ('PUT', USER_ENDPOINT))
        self.assertEqual(call['json'], {'password': 'FreshPassw0rd!'})
        self.assertEqual(call['headers']['Authorization'], 'Bearer ' + SESSION)
        self.assertFalse(call['allow_redirects'])

    def test_rejection_reasons_are_read_from_whatever_field_carries_them(self):
        for field in ('msg', 'message'):
            with self.subTest(field=field):
                reply = Response(422, {'code': 422, 'error_code': 'weak_password',
                                       field: 'Password should be at least 8 characters'})
                state = model_library_confirm.set_password(SESSION, 'abc', transport=Transport(put_reply=reply))
                self.assertEqual(state, 'weak')

    def test_a_failure_that_is_not_about_strength_stays_a_plain_failure(self):
        reply = Response(401, {'code': 401, 'error_code': 'bad_jwt', 'msg': 'invalid audience'})
        state = model_library_confirm.set_password(SESSION, 'FreshPassw0rd!', transport=Transport(put_reply=reply))
        self.assertEqual(state, 'failed')

    def test_a_dead_service_is_offline_and_never_says_done(self):
        state = model_library_confirm.set_password(SESSION, 'FreshPassw0rd!',
                                                   transport=Transport(error=requests.ConnectionError()))
        self.assertEqual(state, 'offline')

    def test_a_200_that_is_not_a_user_object_never_claims_the_password_changed(self):
        for reply in (Response(200, {'session': {'access_token': SESSION}}),
                      Response(200, '<html>proxy said hello</html>')):
            with self.subTest(reply=str(reply.payload)[:20]):
                self.assertEqual(model_library_confirm.set_password(
                    SESSION, 'FreshPassw0rd!', transport=Transport(put_reply=reply)), 'failed')

    def test_a_200_about_some_other_account_is_not_this_users_change(self):
        other = Transport(put_reply=updated('someone.else@example.com'))
        self.assertEqual(model_library_confirm.set_password(
            SESSION, 'FreshPassw0rd!', 'tester@example.com', other), 'failed')
        same = Transport(put_reply=updated('Tester@example.com'))
        self.assertEqual(model_library_confirm.set_password(
            SESSION, 'FreshPassw0rd!', 'tester@example.com', same), 'done')


class Slots(unittest.TestCase):
    def setUp(self):
        model_library_confirm._pending.clear()
        self.addCleanup(model_library_confirm._pending.clear)

    def test_a_slot_hands_back_its_session_exactly_once(self):
        identifier = model_library_confirm.hold(SESSION, 'tester@example.com')
        session, until, email = model_library_confirm.take(identifier)
        self.assertEqual(session, SESSION)
        self.assertEqual(email, 'tester@example.com')
        self.assertGreater(until, time.time())
        self.assertEqual(model_library_confirm.take(identifier), ('', 0, ''))

    def test_the_id_on_the_page_is_not_the_session(self):
        identifier = model_library_confirm.hold(SESSION)
        self.assertNotEqual(identifier, SESSION)
        self.assertTrue(model_library_confirm.SLOT.fullmatch(identifier))

    def test_an_expired_slot_is_retired_on_the_next_touch(self):
        identifier = model_library_confirm.hold(SESSION)
        model_library_confirm._pending[identifier] = (SESSION, time.time() - 1, '')
        self.assertEqual(model_library_confirm.take(identifier), ('', 0, ''))

    def test_give_back_refuses_to_revive_an_expired_slot(self):
        identifier = model_library_confirm.hold(SESSION)
        model_library_confirm._pending[identifier] = (SESSION, time.time() - 1, '')
        model_library_confirm.give_back(identifier, SESSION, time.time() - 1)
        self.assertEqual(model_library_confirm.take(identifier), ('', 0, ''))

    def test_a_storm_of_links_cannot_grow_the_table_past_its_cap(self):
        for _ in range(model_library_confirm.MAX_PENDING + 4):
            model_library_confirm.hold(SESSION)
        self.assertEqual(len(model_library_confirm._pending), model_library_confirm.MAX_PENDING)

    def test_an_open_link_is_reported_for_that_address_only(self):
        identifier = model_library_confirm.hold(SESSION, 'tester@example.com')
        self.assertTrue(model_library_confirm.reset_pending('TESTER@example.com'))
        self.assertFalse(model_library_confirm.reset_pending('someone.else@example.com'))
        self.assertFalse(model_library_confirm.reset_pending(''))
        model_library_confirm.take(identifier)
        self.assertFalse(model_library_confirm.reset_pending('tester@example.com'),
                         'A finished link must stop nagging the next sign-in.')

    def test_a_typo_that_returns_the_slot_keeps_explaining_the_next_sign_in(self):
        identifier = model_library_confirm.hold(SESSION, 'tester@example.com')
        session, until, email = model_library_confirm.take(identifier)
        self.assertFalse(model_library_confirm.reset_pending('tester@example.com'))
        model_library_confirm.give_back(identifier, session, until, email)
        self.assertTrue(model_library_confirm.reset_pending('tester@example.com'))


class Wiring(unittest.TestCase):
    def test_the_page_answers_get_and_refuses_to_become_an_api(self):
        app = FastAPI()
        app.include_router(router(lambda request: True, lambda request: True, transport=Transport()))
        probe = TestClient(app)
        self.assertEqual(probe.get('/api/model-library/confirm').status_code, 200)
        self.assertTrue(probe.get('/api/model-library/confirm').headers['content-type'].startswith('text/html'))
        self.assertEqual(probe.post('/api/model-library/confirm?confirmation_token=' + HASH).status_code, 405)
        self.assertEqual(probe.get('/api/model-library/reset').status_code, 200)
        self.assertEqual(probe.put('/api/model-library/reset').status_code, 405)

    def test_the_shipped_app_resets_a_password_from_a_link_clicked_inside_webmail(self):
        import app as sakura_app
        transport = Transport(reply=recovered())
        with patch.object(model_library_confirm.requests, 'post', transport.post), \
             patch.object(model_library_confirm.requests, 'put', transport.put):
            probe = TestClient(sakura_app.app)
            page = probe.get('/api/model-library/reset?recovery_token=' + HASH,
                             headers={'host': '127.0.0.1:8766', 'sec-fetch-site': 'cross-site',
                                      'referer': 'https://mail.google.com/'})
            self.assertEqual(page.status_code, 200)
            self.assertIn('Choose a new password.', page.text)
            done = probe.post('/api/model-library/reset',
                              data={'reset_id': FIELD.search(page.text).group(1),
                                    'password': 'FreshPassw0rd!', 'confirm': 'FreshPassw0rd!'},
                              headers={'host': '127.0.0.1:8766', 'origin': 'http://127.0.0.1:8766'})
        self.assertEqual(done.status_code, 200)
        self.assertIn('Your password is changed.', done.text)
        self.assertEqual([call for call in transport.calls if call['method'] == 'PUT'][0]['json'],
                         {'password': 'FreshPassw0rd!'})

    def test_the_shipped_app_refuses_a_reset_form_posted_by_another_website(self):
        import app as sakura_app
        transport = Transport(reply=recovered())
        with patch.object(model_library_confirm.requests, 'post', transport.post), \
             patch.object(model_library_confirm.requests, 'put', transport.put):
            probe = TestClient(sakura_app.app)
            page = probe.get('/api/model-library/reset?recovery_token=' + HASH,
                             headers={'host': '127.0.0.1:8766'})
            forged = probe.post('/api/model-library/reset',
                                data={'reset_id': FIELD.search(page.text).group(1),
                                      'password': 'FreshPassw0rd!', 'confirm': 'FreshPassw0rd!'},
                                headers={'host': '127.0.0.1:8766', 'origin': 'http://evil.example'})
        self.assertEqual(forged.status_code, 403)
        self.assertIn('Only this computer', forged.text)
        self.assertEqual([call for call in transport.calls if call['method'] == 'PUT'], [])

    def test_the_shipped_app_confirms_a_link_clicked_inside_webmail(self):
        # A top-level navigation from mail.google.com is cross-site, so a CSRF-style guard
        # here rejects the only request this page exists to serve.
        import app as sakura_app
        transport = Transport()
        headers = {'host': '127.0.0.1:8766', 'sec-fetch-site': 'cross-site',
                   'referer': 'https://mail.google.com/'}
        with patch.object(model_library_confirm.requests, 'post', transport.post):
            response = TestClient(sakura_app.app).get(
                '/api/model-library/confirm?confirmation_token=' + HASH, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Your email address is confirmed.', response.text)
        self.assertEqual(transport.calls[0]['json'], {'type': 'signup', 'token_hash': HASH})

    def test_the_shipped_app_refuses_a_page_served_on_someother_address(self):
        import app as sakura_app
        transport = Transport()
        with patch.object(model_library_confirm.requests, 'post', transport.post):
            response = TestClient(sakura_app.app).get(
                '/api/model-library/confirm?confirmation_token=' + HASH,
                headers={'host': 'attacker.example', 'sec-fetch-site': 'none'})
        self.assertEqual(response.status_code, 403)
        self.assertIn('Only this computer', response.text)
        self.assertEqual(transport.calls, [])


if __name__ == '__main__':
    unittest.main()
