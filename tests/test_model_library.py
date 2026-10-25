import hashlib
import io
import json
import time
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import zipfile

import requests
from fastapi.testclient import TestClient
from model_library import ModelLibrary, library_url
from model_library_config import LIBRARY_URL
from model_library_server import create_app

TOKEN = 'test_member_access_' + 'a' * 32


def package(unsafe=False):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('../escape.txt' if unsafe else 'Model/model.model3.json', json.dumps({
            'Version': 3, 'FileReferences': {'Moc': 'model.moc3', 'Textures': ['tex/0.png']}}))
        archive.writestr('Model/model.moc3', b'MOC3' + b'\0' * 32)
        archive.writestr('Model/tex/0.png', b'test-texture')
    return output.getvalue()


class Response:
    def __init__(self, response):
        self.response = response
        self.status_code = response.status_code

    def close(self):
        self.response.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def iter_content(self, size):
        yield from self.response.iter_bytes(size)


class Transport:
    def __init__(self, client):
        self.client = client

    def get(self, url, headers, **kwargs):
        return Response(self.client.get(url.replace('http://localhost', ''), headers=headers))


class ModelLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / 'host'
        self.store.mkdir()
        self.members = self.root / 'members.json'
        self.members.write_text(json.dumps({'tester': hashlib.sha256(TOKEN.encode()).hexdigest()}))
        self.blob = package()
        self.write_catalogue()
        self.web = TestClient(create_app(self.store, self.members))
        self.addCleanup(self.web.close)
        self.client = ModelLibrary(self.root / 'models', lambda: {'url': 'http://localhost', 'token': TOKEN}, Transport(self.web))

    def write_catalogue(self, digest=None):
        entry = {'id': 'live2d-test', 'name': 'Test character', 'format': 'live2d', 'bytes': len(self.blob),
                 'sha256': digest or hashlib.sha256(self.blob).hexdigest(), 'version': '1', 'mobile_compatible': True}
        (self.store / 'catalogue.json').write_text(json.dumps({'models': [entry]}))
        (self.store / 'live2d-test.zip').write_bytes(self.blob)

    def test_anonymous_download_and_catalogue_are_private(self):
        for path in ('/v1/models', '/v1/models/live2d-test/package', '/catalogue.json', '/docs'):
            self.assertEqual(401, self.web.get(path).status_code)
        self.assertEqual(401, self.web.get('/v1/models?token=' + TOKEN).status_code)

    def test_real_download_validates_imports_and_does_not_overwrite_edits(self):
        self.assertFalse(self.client.catalogue()['models'][0]['installed'])
        result = self.client.install('live2d-test')
        descriptor = self.root / 'models' / result['models'][0]
        self.assertTrue(descriptor.is_file())
        self.assertTrue((descriptor.parent / 'tex/0.png').is_file())
        descriptor.write_text('user edits')
        self.assertTrue(self.client.install('live2d-test')['already_installed'])
        self.assertEqual('user edits', descriptor.read_text())
        self.assertTrue(self.client.catalogue()['models'][0]['installed'])

    def test_hash_mismatch_installs_nothing(self):
        self.write_catalogue('0' * 64)
        with self.assertRaisesRegex(ValueError, 'integrity'):
            self.client.install('live2d-test')
        self.assertFalse((self.root / 'models').exists())

    def test_valid_hash_cannot_bypass_archive_path_guard(self):
        self.blob = package(unsafe=True)
        self.write_catalogue()
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            self.client.install('live2d-test')
        self.assertFalse((self.root / 'escape.txt').exists())

    def test_revoking_member_blocks_existing_client(self):
        self.members.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'refused'):
            self.client.catalogue()

    def test_endpoint_validation_disallows_cleartext_and_embedded_secrets(self):
        for endpoint in ('http://example.com', 'https://user:pass@example.com', 'https://example.com?token=secret', 'file:///tmp/library'):
            with self.assertRaises(ValueError):
                library_url(endpoint)

    @patch.dict('os.environ', {'SAKURA_LIBRARY_SUPABASE_URL': 'https://example.supabase.co', 'SAKURA_LIBRARY_SUPABASE_PUBLISHABLE_KEY': 'publishable-test'})
    @patch('model_library_server.requests.request')
    def test_supabase_verifies_sessions_with_provider_not_jwt_claims(self, request):
        self.members.write_text('{}')
        request.return_value = Mock(status_code=200, json=lambda: {'id': 'member-id', 'email_confirmed_at': '2026-10-25'})
        headers = {'Authorization': 'Bearer ' + 'x' * 80}
        self.assertEqual(200, self.web.get('/v1/models', headers=headers).status_code)
        self.assertEqual('https://example.supabase.co/auth/v1/user', request.call_args.args[1])
        request.return_value = Mock(status_code=401)
        self.assertEqual(401, self.web.get('/v1/models', headers=headers).status_code)

    @patch.dict('os.environ', {'SAKURA_LIBRARY_SUPABASE_URL': 'https://example.supabase.co', 'SAKURA_LIBRARY_SUPABASE_PUBLISHABLE_KEY': 'publishable-test'})
    @patch('model_library_server.requests.request')
    def test_registration_delegates_to_supabase_and_requires_email_confirmation(self, request):
        request.return_value = Mock(status_code=200, json=lambda: {'id': 'new-member'})
        response = self.web.post('/v1/auth/signup', json={'email': 'tester@example.com', 'password': 'a-good-test-password'})
        self.assertTrue(response.json()['confirmation_required'])
        self.assertEqual('https://example.supabase.co/auth/v1/signup', request.call_args.args[1])
        self.assertEqual(400, self.web.post('/v1/auth/signup', json=[]).status_code)

    def test_server_never_serves_an_unlisted_archive(self):
        (self.store / 'unlisted.zip').write_bytes(b'secret')
        response = self.web.get('/v1/models/unlisted/package', headers={'Authorization': 'Bearer ' + TOKEN})
        self.assertEqual(404, response.status_code)

    def test_desktop_router_hides_credentials_and_guards_mutations(self):
        from fastapi import FastAPI
        from model_library import router
        with patch('agent_connections.secret_get', return_value={'url': 'https://library.example.com', 'token': TOKEN}):
            app = FastAPI()
            app.include_router(router(self.root / 'models', lambda request: request.headers.get('x-local-test') == 'yes'))
            with TestClient(app) as client:
                self.assertEqual(403, client.post('/api/model-library/connection', json={'disconnect': True}).status_code)
                response = client.get('/api/model-library/connection', headers={'x-local-test': 'yes'})
                self.assertEqual(200, response.status_code)
                self.assertNotIn(TOKEN, response.text)
                self.assertEqual(403, client.post('/api/model-library/models/example/install').status_code)

    @patch('model_library.requests.post')
    def test_desktop_signup_explains_email_sender_restriction(self, post):
        from fastapi import FastAPI
        from model_library import router
        post.return_value.__enter__.return_value = Mock(status_code=403, json=lambda: {'code': 'email_address_not_authorized', 'msg': 'private provider detail'})
        app = FastAPI()
        app.include_router(router(self.root / 'models', lambda request: True))
        with TestClient(app) as client:
            response = client.post('/api/model-library/account/signup', json={'email': 'tester@example.com', 'password': 'password-for-test'})
        self.assertEqual(400, response.status_code)
        self.assertIn('verification-email sender', response.json()['error'])
        self.assertNotIn('private provider detail', response.text)

    @patch('model_library.requests.post')
    def test_desktop_signup_accepts_created_status_and_requests_confirmation(self, post):
        from fastapi import FastAPI
        from model_library import router
        post.return_value.__enter__.return_value = Mock(status_code=201, json=lambda: {'user': {'id': 'new-user'}})
        app = FastAPI()
        app.include_router(router(self.root / 'models', lambda request: True))
        with TestClient(app) as client:
            response = client.post('/api/model-library/account/signup', json={'email': ' tester@example.com ', 'password': 'password-for-test'})
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()['confirmation_required'])
        self.assertEqual('tester@example.com', post.call_args.kwargs['json']['email'])

    @patch('model_library.requests.post')
    def test_invalid_signup_does_not_contact_auth_provider(self, post):
        from fastapi import FastAPI
        from model_library import router
        app = FastAPI()
        app.include_router(router(self.root / 'models', lambda request: True))
        with TestClient(app) as client:
            response = client.post('/api/model-library/account/signup', json={'email': '', 'password': ''})
        self.assertIn('at least 8', response.json()['error'])
        post.assert_not_called()

    @patch('model_library.requests.post')
    def test_desktop_recovery_sends_a_link_and_leaves_the_saved_session_alone(self, post):
        from fastapi import FastAPI
        from model_library import router
        post.return_value.__enter__.return_value = Mock(status_code=200, json=lambda: {'message': 'private provider detail'})
        saved = []
        with patch('agent_connections.secret_set', side_effect=lambda *args: saved.append(args)):
            app = FastAPI()
            app.include_router(router(self.root / 'models', lambda request: True))
            with TestClient(app) as client:
                response = client.post('/api/model-library/account/recover', json={'email': 'tester@example.com'})
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()['reset_sent'])
        self.assertNotIn('private provider detail', response.text)
        self.assertTrue(post.call_args.args[0].endswith('/auth/v1/recover'))
        self.assertEqual(post.call_args.kwargs['json'], {'email': 'tester@example.com'})
        self.assertEqual(saved, [])

    @patch('model_library.requests.post')
    def test_invalid_recovery_email_does_not_contact_auth_provider(self, post):
        from fastapi import FastAPI
        from model_library import router
        app = FastAPI()
        app.include_router(router(self.root / 'models', lambda request: True))
        with TestClient(app) as client:
            response = client.post('/api/model-library/account/recover', json={'email': 'not-an-email'})
        self.assertEqual(400, response.status_code)
        self.assertIn('email address you created', response.json()['error'])
        post.assert_not_called()

    @patch('model_library.requests.post')
    def test_custom_library_answer_without_a_session_is_not_called_a_password_problem(self, post):
        from fastapi import FastAPI
        from model_library import router
        post.return_value.__enter__.return_value = Mock(status_code=200, json=lambda: {'ok': True})
        saved = []
        with patch('agent_connections.secret_set', side_effect=lambda *args: saved.append(args)):
            app = FastAPI()
            app.include_router(router(self.root / 'models', lambda request: True))
            with TestClient(app) as client:
                response = client.post('/api/model-library/account/signin', json={'url': 'https://library.example.com', 'email': 'tester@example.com', 'password': 'password-for-test'})
        self.assertEqual(400, response.status_code)
        self.assertIn('without a session', response.json()['error'])
        self.assertNotIn('email confirmation', response.text)
        self.assertEqual(saved, [])

    @patch('model_library.requests.post')
    def test_custom_library_answer_with_an_incomplete_session_blames_the_library_not_the_user(self, post):
        from fastapi import FastAPI
        from model_library import router
        for answer in ({'access_token': 'a-session-token-' + 'b' * 24},
                       {'access_token': 'a-session-token-' + 'b' * 24, 'refresh_token': 'a-refresh-token-' + 'c' * 24},
                       {'access_token': 'a-session-token-' + 'b' * 24, 'refresh_token': 'a-refresh-token-' + 'c' * 24, 'expires_in': 'soon'}):
            with self.subTest(answer=sorted(answer)):
                post.return_value.__enter__.return_value = Mock(status_code=200, json=lambda: answer)
                saved = []
                with patch('agent_connections.secret_set', side_effect=lambda *args: saved.append(args)):
                    app = FastAPI()
                    app.include_router(router(self.root / 'models', lambda request: True))
                    with TestClient(app) as client:
                        response = client.post('/api/model-library/account/signin', json={'url': 'https://library.example.com', 'email': 'tester@example.com', 'password': 'password-for-test'})
                self.assertEqual(400, response.status_code)
                self.assertIn('incomplete session', response.json()['error'])
                self.assertIn('library address', response.json()['error'])
                self.assertEqual(saved, [])

    @patch('model_library.ModelLibrary.catalogue', return_value={'models': []})
    @patch('model_library.requests.post')
    def test_custom_library_answer_with_a_full_session_still_signs_in(self, post, catalogue):
        from fastapi import FastAPI
        from model_library import router
        post.return_value.__enter__.return_value = Mock(status_code=200, json=lambda: {
            'access_token': 'a-session-token-' + 'b' * 24, 'refresh_token': 'a-refresh-token-' + 'c' * 24, 'expires_in': 3600})
        saved = []
        with patch('agent_connections.secret_set', side_effect=lambda *args: saved.append(args)):
            app = FastAPI()
            app.include_router(router(self.root / 'models', lambda request: True))
            with TestClient(app) as client:
                response = client.post('/api/model-library/account/signin', json={'url': 'https://library.example.com/', 'email': 'tester@example.com', 'password': 'password-for-test'})
        self.assertEqual(200, response.status_code)
        self.assertEqual('a-session-token-' + 'b' * 24, saved[0][1]['token'])
        self.assertTrue(saved[0][1]['expires_at'] > time.time())

    @patch('model_library.requests.post')
    def test_a_library_refresh_without_a_session_is_a_message_not_a_crash(self, post):
        from fastapi import FastAPI
        from model_library import router
        post.return_value.__enter__.return_value = Mock(status_code=200, json=lambda: {'ok': True})
        expired = {'url': 'https://library.example.com', 'token': 'old-' + 'd' * 32,
                   'refresh_token': 'old-' + 'e' * 32, 'expires_at': time.time() - 1}
        with patch('agent_connections.secret_get', return_value=dict(expired)):
            app = FastAPI()
            app.include_router(router(self.root / 'models', lambda request: True))
            with TestClient(app) as client:
                response = client.get('/api/model-library/models')
        self.assertEqual(400, response.status_code)
        self.assertIn('Cannot read the library', response.json()['error'])
        self.assertNotIn('without a session', response.text)

    def test_the_connection_reply_names_the_cloud_so_a_self_hosted_address_stands_out(self):
        from fastapi import FastAPI
        from model_library import router
        with patch('agent_connections.secret_get', return_value={'url': LIBRARY_URL, 'token': TOKEN}):
            app = FastAPI()
            app.include_router(router(self.root / 'models', lambda request: True))
            with TestClient(app) as client:
                response = client.get('/api/model-library/connection')
        self.assertEqual(response.json()['cloud'], LIBRARY_URL)
        self.assertNotIn(TOKEN, response.text)

    @patch('model_library.requests.post')
    def test_an_emailed_link_is_declared_unreachable_while_the_port_is_rolled(self, post):
        from fastapi import FastAPI
        from model_library import router
        post.return_value.__enter__.return_value = Mock(status_code=200, json=lambda: {'user': {'id': 'new-user'}})
        app = FastAPI()
        app.include_router(router(self.root / 'models', lambda request: True))
        for path, body in (('signup', {'email': 'tester@example.com', 'password': 'password-for-test'}),
                           ('recover', {'email': 'tester@example.com'})):
            with self.subTest(action=path):
                with TestClient(app, base_url='http://127.0.0.1:8767') as rolled, \
                        TestClient(app, base_url='http://127.0.0.1:8766') as pinned:
                    warning = rolled.post('/api/model-library/account/' + path, json=body).json()['message']
                    quiet = pinned.post('/api/model-library/account/' + path, json=body).json()['message']
                self.assertIn('port 8767 instead of 8766', warning)
                self.assertIn('request a fresh email', warning)
                self.assertNotIn('8767', quiet)

    @patch('model_library.requests.post')
    def test_a_library_address_problem_keeps_its_own_explanation(self, post):
        from fastapi import FastAPI
        from model_library import router
        app = FastAPI()
        app.include_router(router(self.root / 'models', lambda request: True))
        with TestClient(app) as client:
            response = client.post('/api/model-library/account/signin',
                                   json={'url': 'https://library.example.com/download', 'email': 'tester@example.com', 'password': 'password-for-test'})
        self.assertEqual(400, response.status_code)
        self.assertIn('without a path', response.json()['error'])
        self.assertNotIn('password and email confirmation', response.text)
        post.assert_not_called()

    @patch('model_library.requests.post')
    def test_an_unreadable_answer_blames_the_service_not_the_password(self, post):
        from fastapi import FastAPI
        from model_library import router
        for failure in (ValueError('provider detail'),
                        requests.exceptions.JSONDecodeError('provider detail', '<html>not json</html>', 0)):
            with self.subTest(failure=type(failure).__name__):
                post.return_value.__enter__.return_value = Mock(status_code=200, json=Mock(side_effect=failure))
                app = FastAPI()
                app.include_router(router(self.root / 'models', lambda request: True))
                with TestClient(app) as client:
                    response = client.post('/api/model-library/account/signin',
                                           json={'email': 'tester@example.com', 'password': 'password-for-test'})
                self.assertEqual(400, response.status_code)
                self.assertIn('could not read the answer', response.json()['error'])
                self.assertNotIn('password', response.json()['error'])
                self.assertNotIn('internet connection', response.text, 'A reachable service is not a dead network.')
                self.assertNotIn('provider detail', response.text)

    @patch('model_library.ModelLibrary.catalogue', side_effect=ValueError('Library access was refused. Check your access code with the library owner.'))
    @patch('model_library.requests.post')
    def test_a_signed_in_library_that_refuses_its_catalogue_says_which_part_failed(self, post, catalogue):
        from fastapi import FastAPI
        from model_library import router
        post.return_value.__enter__.return_value = Mock(status_code=200, json=lambda: {
            'access_token': 'a-session-token-' + 'b' * 24, 'refresh_token': 'a-refresh-token-' + 'c' * 24, 'expires_in': 3600})
        saved = []
        with patch('agent_connections.secret_set', side_effect=lambda *args: saved.append(args)):
            app = FastAPI()
            app.include_router(router(self.root / 'models', lambda request: True))
            with TestClient(app) as client:
                response = client.post('/api/model-library/account/signin',
                                       json={'url': 'https://library.example.com', 'email': 'tester@example.com', 'password': 'password-for-test'})
        self.assertEqual(400, response.status_code)
        self.assertIn('access code', response.json()['error'])
        self.assertEqual(saved, [])


if __name__ == '__main__':
    unittest.main()
