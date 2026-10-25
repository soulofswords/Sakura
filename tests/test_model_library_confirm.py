import unittest
from unittest.mock import patch

import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient

import model_library_confirm
from model_library_confirm import CONFIRM_ENDPOINT, router, verify
from model_library_config import SUPABASE_PUBLISHABLE_KEY

HASH = 'sF4d2sG7hJ0kL9pQrT3vW6xZ1cB5nM8a'
CODE = '123456'


class Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = payload if payload is not None else {'session': {'access_token': 'sess-' + 'x' * 40}}
        self.closed = False

    def json(self):
        return self.payload

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Transport:
    def __init__(self, reply=None, error=None):
        self.calls = []
        self.reply = reply if reply is not None else Response()
        self.error = error

    def post(self, url, json=None, headers=None, timeout=None, allow_redirects=None):
        self.calls.append({'url': url, 'json': json, 'headers': headers,
                           'timeout': timeout, 'allow_redirects': allow_redirects})
        if self.error:
            raise self.error
        return self.reply


def client(local=True, transport=None):
    app = FastAPI()
    app.include_router(router(lambda request: local, transport=transport or Transport()))
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


class Wiring(unittest.TestCase):
    def test_the_page_answers_get_and_refuses_to_become_an_api(self):
        app = FastAPI()
        app.include_router(router(lambda request: True, transport=Transport()))
        probe = TestClient(app)
        self.assertEqual(probe.get('/api/model-library/confirm').status_code, 200)
        self.assertTrue(probe.get('/api/model-library/confirm').headers['content-type'].startswith('text/html'))
        self.assertEqual(probe.post('/api/model-library/confirm?confirmation_token=' + HASH).status_code, 405)

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
