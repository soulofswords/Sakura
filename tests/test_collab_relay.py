import unittest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from collab_relay.app import app, rooms, room_locks


class CollabRelayTests(unittest.TestCase):
    def setUp(self):
        rooms.clear()
        room_locks.clear()
        self.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['service'], 'sakura-collab-relay')

    def test_only_two_peers_and_signaling_is_relayed(self):
        room = 'TESTROOM88'
        with self.client.websocket_connect(f'/ws/{room}') as host:
            host.send_json({'type': 'join', 'peer': 'host'})
            self.assertTrue(host.receive_json()['initiator'])
            with self.client.websocket_connect(f'/ws/{room}') as guest:
                guest.send_json({'type': 'join', 'peer': 'guest'})
                self.assertFalse(guest.receive_json()['initiator'])
                self.assertEqual(host.receive_json()['type'], 'peer_joined')
                guest.send_json({'type': 'offer', 'to': 'host', 'data': {'sdp': 'example'}})
                self.assertEqual(host.receive_json(), {'type': 'offer', 'from': 'guest', 'data': {'sdp': 'example'}})
                with self.client.websocket_connect(f'/ws/{room}') as third:
                    third.send_json({'type': 'join', 'peer': 'third'})
                    self.assertEqual(third.receive_json()['type'], 'joined')
                    self.assertEqual(host.receive_json(), {'type': 'peer_joined', 'peer': 'third'})
                    self.assertEqual(guest.receive_json(), {'type': 'peer_joined', 'peer': 'third'})

    def test_room_capacity_is_six(self):
        room = 'SIXROOM888'
        with self.client.websocket_connect(f'/ws/{room}') as first:
            first.send_json({'type': 'join', 'peer': 'p0'})
            first.receive_json()
            sockets = []
            try:
                for index in range(1, 6):
                    socket = self.client.websocket_connect(f'/ws/{room}')
                    sockets.append(socket)
                    socket.__enter__()
                    socket.send_json({'type': 'join', 'peer': f'p{index}'})
                    socket.receive_json()
                with self.client.websocket_connect(f'/ws/{room}') as seventh:
                    seventh.send_json({'type': 'join', 'peer': 'p6'})
                    self.assertEqual(seventh.receive_json()['type'], 'room_full')
            finally:
                for socket in reversed(sockets):
                    socket.__exit__(None, None, None)

    def test_bad_room_code_is_rejected(self):
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect('/ws/short') as socket:
                socket.receive_text()


if __name__ == '__main__':
    unittest.main()
