import unittest
import itertools
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from cursor_stream import install_cursor_stream


class CursorStreamTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        install_cursor_stream(app)
        self.client = TestClient(app, base_url='http://127.0.0.1:8766')

    def test_latest_position_is_sent_on_one_connection(self):
        with patch('cursor_stream.position', side_effect=itertools.chain([{'x': .2, 'y': -.3}], itertools.repeat({'x': .8, 'y': .1}))):
            with self.client.websocket_connect('ws://127.0.0.1:8766/api/cursor/stream', headers={'origin': 'http://127.0.0.1:8766'}) as socket:
                self.assertEqual(socket.receive_json(), {'x': .2, 'y': -.3})
                self.assertEqual(socket.receive_json(), {'x': .8, 'y': .1})

    def test_external_websites_and_other_local_ports_cannot_read_the_cursor(self):
        for origin in ('https://example.com', 'http://127.0.0.1:9999', 'null', ''):
            with self.subTest(origin=origin), self.assertRaises(WebSocketDisconnect):
                with self.client.websocket_connect('ws://127.0.0.1:8766/api/cursor/stream', headers={'origin': origin}):
                    self.fail('An untrusted origin was accepted')
