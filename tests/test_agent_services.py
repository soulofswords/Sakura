import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from agent_connections import Connections, mcp_request
from agent_runtime import digest


class BuiltinServiceTests(unittest.TestCase):
    def test_mcp_discovery_and_real_protocol_call_share_account_binding(self):
        config = {'id': 'a' * 32, 'name': 'Google Calendar', 'transport': 'builtin', 'service': 'google-calendar'}
        with patch('agent_service_mcp.binding', return_value='account-one'), patch('agent_connections.secret_get', return_value={}), \
             patch('agent_calendar.google_calendar.list_events', return_value={'events': [], 'ok': True}) as read:
            tools = mcp_request(config, 'discover')
            read.assert_not_called()
            spec = next(t for t in tools if t['name'] == 'calendar.events.list')
            self.assertEqual('account-one', spec['inputSchema']['properties']['account_binding']['const'])
            result = mcp_request(config, 'call', tool=spec['name'], arguments={'account_binding': 'account-one'}, schema_hash=digest(spec['inputSchema']))
            self.assertFalse(result['is_error'])
            self.assertIn('events', json.dumps(result))
            read.assert_called_once_with()
        with patch('agent_service_mcp.binding', return_value='account-two'), patch('agent_connections.secret_get', return_value={}):
            with self.assertRaises(Exception):
                mcp_request(config, 'call', tool=spec['name'], arguments={'account_binding': 'account-one'}, schema_hash=digest(spec['inputSchema']))

    def test_adapters_expose_only_the_selected_service(self):
        from agent_service_mcp import tool_specs
        with patch('agent_service_mcp.binding', return_value='account-one'):
            for service, prefix in [('google-calendar', 'calendar.'), ('google-drive', 'google.'), ('linkedin', 'linkedin.')]:
                specs = tool_specs(service)
                self.assertTrue(specs)
                self.assertTrue(all(t['name'].startswith(prefix) for t in specs))

    def test_builtin_config_cannot_inject_executables_or_credentials(self):
        with tempfile.TemporaryDirectory() as directory, patch('agent_connections.secret_get', return_value={}), patch('agent_connections.secret_set'):
            connections = Connections(Path(directory) / 'connections.json')
            item = connections.save({'name': 'Google Calendar', 'transport': 'builtin', 'service': 'google-calendar', 'command': 'untrusted.exe'})
            self.assertNotIn('command', item)
            with self.assertRaises(ValueError):
                connections.save({'name': 'Fake', 'transport': 'builtin', 'service': 'unknown'})
            with self.assertRaises(ValueError):
                connections.save({'name': 'Fake', 'transport': 'builtin', 'service': 'linkedin', 'token': 'secret'})

    def test_service_routes_require_local_token_and_reuse_existing_preset(self):
        import re
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from agent_api import agent_router
        from agent_runtime import AgentRuntime
        with tempfile.TemporaryDirectory() as directory, patch('agent_connections.secret_get', return_value={}), patch('agent_connections.secret_set'):
            runtime = AgentRuntime(Connections(Path(directory) / 'connections.json'))
            with patch('agent_api.runtime', runtime):
                app = FastAPI(); app.include_router(agent_router(lambda: None))
                with TestClient(app, base_url='http://127.0.0.1:8790', client=('127.0.0.1', 35000)) as client:
                    token = re.search(r"const token='([^']+)'", client.get('/agent').text)[1]
                    headers = {'X-Sakura-Agent': token}
                    self.assertEqual(403, client.post('/api/agent/services/google-drive', json={}).status_code)
                    first = client.post('/api/agent/services/google-drive', headers=headers, json={}).json()
                    second = client.post('/api/agent/services/google-drive', headers=headers, json={}).json()
                    self.assertEqual(first['id'], second['id'])
                    with patch('agent_calendar.google_calendar.authorize', return_value='https://accounts.google.com/example') as connect, patch('webbrowser.open', return_value=True):
                        response = client.post('/api/agent/services/google-drive/connect', headers=headers, json={})
                    self.assertTrue(response.json()['opened'])
                    connect.assert_called_once_with(True)
                    self.assertEqual(400, client.post('/api/agent/services/unknown', headers=headers, json={}).status_code)
