"""A setup goal that ends in a browser tab needs a server that outlives its own step."""
import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import psutil

import local_serve_tools as serve
from agent_connections import Connections
from agent_runtime import AUTO_RUN_TOOLS, AgentRuntime


class _Reply(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b"<title>Local App</title>")

    def log_message(self, *args):
        pass


class UrlTests(unittest.TestCase):
    def test_ipv6_only_server_opens_the_address_that_actually_answers(self):
        class IPv6Server(HTTPServer):
            address_family = socket.AF_INET6
        try:
            server = IPv6Server(('::1', 0), _Reply)
        except OSError as error:
            self.skipTest('IPv6 loopback unavailable: ' + str(error))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        port = server.server_address[1]
        with patch('local_serve_tools.webbrowser.open', return_value=True) as opened:
            result = serve.open_when_ready('http://127.0.0.1:%d/?check=1' % port, 3)
        self.assertTrue(result['ok'])
        self.assertEqual(result['url'], 'http://[::1]:%d/?check=1' % port)
        opened.assert_called_once_with(result['url'], 1, True)
        self.assertEqual(serve.local_url(result['url'])['host'], '::1')

    def test_only_this_computer_can_be_opened(self):
        self.assertEqual(serve.local_url('http://localhost:4173/setup?q=1')['url'], 'http://127.0.0.1:4173/setup?q=1')
        self.assertEqual(serve.local_url('http://0.0.0.0:8000')['port'], 8000)
        for refused in ['https://example.com/', 'file:///C:/Windows/win.ini', 'http://192.168.1.9:3000/',
                        'http://admin:pw@127.0.0.1/', 'not-a-url', '']:
            with self.subTest(refused):
                with self.assertRaises(ValueError):
                    serve.local_url(refused)


class WaitTests(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(('127.0.0.1', 0), _Reply)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.port = self.server.server_address[1]
        # Registered in that order so cleanup stops the loop before closing its socket.
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def test_a_server_that_answers_is_detected_and_opened_once(self):
        with patch('local_serve_tools.webbrowser.open', return_value=True) as opened:
            result = serve.open_when_ready('http://localhost:%d/' % self.port, 10)
        self.assertTrue(result['ok'] and result['opened'] and result['status'] == 200)
        opened.assert_called_once_with('http://127.0.0.1:%d/' % self.port, 1, True)

    def test_in_app_open_never_launches_system_browser(self):
        with patch('local_serve_tools.webbrowser.open') as opened:
            result = serve.open_when_ready('http://localhost:%d/' % self.port, 10, in_app=True)
        self.assertTrue(result['ok'] and result['view_requested'])
        self.assertFalse(result['opened'])
        self.assertEqual(result['presentation'], 'sakura-browser')
        opened.assert_not_called()

    def test_an_absent_server_reports_the_wait_instead_of_opening_anything(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        listener.close()
        with patch('local_serve_tools.webbrowser.open') as opened:
            result = serve.open_when_ready('http://127.0.0.1:%d/' % port, 2)
        self.assertFalse(result['ok'] or result['opened'])
        self.assertFalse(result['answered'])
        opened.assert_not_called()

    def test_a_browser_with_no_handler_is_said_out_loud(self):
        with patch('local_serve_tools.webbrowser.open', return_value=False):
            result = serve.open_when_ready('http://127.0.0.1:%d/' % self.port, 10)
        self.assertTrue(result['answered'])
        self.assertFalse(result['ok'] or result['opened'])
        self.assertIn('default browser', result['error'])


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.runtime = AgentRuntime(Connections(self.root / 'connections.json'))
        self.run = self.runtime.new_run('Set up this repository and open it', str(self.root))
        self.pids = []
        self.addCleanup(self._kill_started)

    def _kill_started(self):
        """The served process holds its own log open, so the temp workspace can only be removed
        once Windows has actually released it."""
        for pid in self.pids:
            try:
                target = psutil.Process(pid)
            except psutil.NoSuchProcess:
                continue
            tree = [target] + target.children(recursive=True)
            for child in tree:
                try:
                    child.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                    pass
            psutil.wait_procs(tree, timeout=15)

    def test_a_served_command_survives_its_own_step(self):
        """shell.run waits and then kills its tree, so a dev server started there is gone when the
        step ends. shell.serve has to leave the process running and put its output in the workspace."""
        action = self.runtime._prepare(self.run, 'shell.serve',
                                       {'command': "Write-Output 'listening on 4173'; Start-Sleep -Seconds 60",
                                        'log_file': 'gev.log'})
        # The reviewer sees the exact command and where its output will land.
        self.assertEqual(action['preview']['command'], "Write-Output 'listening on 4173'; Start-Sleep -Seconds 60")
        self.assertIn('Start-Sleep', action['preview']['command'])
        self.assertTrue(action['bindings']['log'].endswith('gev.log'))
        self.assertTrue(Path(action['bindings']['log']).is_relative_to(self.root))
        result = self.runtime._execute(action, self.run)
        self.pids.append(result['pid'])
        self.assertTrue(result['ok'] and result['detached'])
        log = Path(result['log'])
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and 'listening' not in (log.read_text(errors='replace') if log.is_file() else ''):
            time.sleep(0.2)
        self.assertIn('listening on 4173', log.read_text(errors='replace'))
        self.assertTrue(psutil.pid_exists(result['pid']))

    def test_open_is_auto_approved_and_only_for_a_loopback_address(self):
        server = HTTPServer(('127.0.0.1', 0), _Reply)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        port = server.server_address[1]
        self.assertIn('local_app.open', AUTO_RUN_TOOLS)
        self.assertNotIn('shell.serve', AUTO_RUN_TOOLS)
        action = self.runtime._prepare(self.run, 'local_app.open', {'url': 'http://localhost:%d/' % port, 'wait_seconds': 10})
        self.assertEqual(action['bindings']['target'], 'http://127.0.0.1:%d/' % port)
        self.assertTrue(self.runtime._auto_allowed(action))
        with patch('local_serve_tools.webbrowser.open', return_value=True) as opened:
            result = self.runtime._execute(action, self.run)
        self.assertTrue(result['ok'] and result['view_requested'])
        self.assertEqual(result['presentation'], 'sakura-browser')
        self.assertFalse(result['opened'])
        opened.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'not accepted'):
            self.runtime._prepare(self.run, 'local_app.open', {'url': 'https://example.com/'})

    def test_the_server_log_lives_inside_the_task_workspace(self):
        """The log name comes from the planner, so it is reduced to one basename before being placed
        in the workspace: a folder the reviewer approved cannot be traded for a write outside it."""
        escaped = serve.serve_log(self.root, '../../escape')
        self.assertTrue(str(escaped).startswith(str(self.root)))
        self.assertEqual(escaped.name, 'escape.log')
        nested = serve.serve_log(self.root, 'nested/name.log')
        self.assertTrue(str(nested).startswith(str(self.root)))
        self.assertEqual(nested.name, 'name.log')
        self.assertEqual(serve.serve_log(self.root, None).name, 'serve.log')


if __name__ == '__main__':
    unittest.main()
