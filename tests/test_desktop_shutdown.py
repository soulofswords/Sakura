import subprocess
import sys
import unittest
from pathlib import Path

class ShutdownTests(unittest.TestCase):
    def test_busy_executor_does_not_keep_closed_app_running(self):
        root = Path(__file__).resolve().parents[1]
        code = """
import threading, time
from desktop_shutdown import arm_shutdown
threading.Thread(target=lambda: time.sleep(60)).start()
arm_shutdown(lambda: time.sleep(60), timeout=.2)
time.sleep(60)
"""
        result = subprocess.run([sys.executable, '-c', code], cwd=root, timeout=5)
        self.assertEqual(result.returncode, 0)

    def test_cleanup_runs_before_successful_exit(self):
        import threading
        from desktop_shutdown import arm_shutdown
        exited = threading.Event()
        calls = []
        arm_shutdown(lambda: calls.append('cleanup'), timeout=1,
                     exit_process=lambda code: (calls.append(code), exited.set()))
        self.assertTrue(exited.wait(2))
        self.assertEqual(calls, ['cleanup', 0])
