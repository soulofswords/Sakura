import json
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_connections import mcp_request
from agent_runtime import digest


FIXTURE=Path(__file__).parent/'fixtures/agent_mcp_server.py'


class RealMCPTests(unittest.TestCase):
    def check_transport(self,config):
        with patch('agent_connections.secret_get',return_value={}):
            tools=mcp_request(config,'discover')
            echo=next(tool for tool in tools if tool['name']=='echo')
            result=mcp_request(config,'call',tool='echo',arguments={'text':'reviewed input'},schema_hash=digest(echo['inputSchema']))
            self.assertIn('Approved echo: reviewed input',json.dumps(result))
            self.assertFalse(result['is_error'])
            with self.assertRaises(Exception):mcp_request(config,'call',tool='echo',arguments={'text':'reviewed'},schema_hash='outdated-schema')
    def test_real_stdio_initialize_discover_call_and_schema_binding(self):
        config={'id':'a'*32,'name':'Test','transport':'stdio','command':sys.executable,'args':[str(FIXTURE)]}
        self.check_transport(config)
    def test_real_http_initialize_discover_call_and_schema_binding(self):
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        process=subprocess.Popen([sys.executable,str(FIXTURE),'http',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        try:
            ready=False
            for _ in range(60):
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.1):ready=True;break
                except OSError:time.sleep(.1)
            self.assertTrue(ready,'MCP fixture HTTP server did not start')
            self.check_transport({'id':'b'*32,'name':'HTTP test','transport':'http','url':f'http://127.0.0.1:{port}/mcp'})
        finally:
            process.terminate();process.wait(timeout=5)
