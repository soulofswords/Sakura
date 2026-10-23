import io
import tempfile
import unittest
from pathlib import Path

from nvidia_ar_feature_installer import FeatureInstaller, REQUIRED_FEATURES


class FakeProcess:
    def __init__(self, *args, **kwargs):
        self.stdout = io.StringIO("Downloading face model\nInstallation Complete\n")
        self.code = 0

    def poll(self):
        return self.code

    def wait(self):
        return self.code


class NvidiaFeatureInstallerTests(unittest.TestCase):
    def _sdk(self, root):
        script = Path(root) / "features" / "install_feature.ps1"
        script.parent.mkdir(parents=True)
        script.write_text("# NVIDIA SDK installer", encoding="utf-8")
        return root

    def test_passes_ngc_key_only_to_child_environment_and_requests_required_features(self):
        captured = {}

        def popen(args, **kwargs):
            captured["args"] = args
            captured["env"] = dict(kwargs["env"])
            return FakeProcess()

        with tempfile.TemporaryDirectory() as temp:
            installer = FeatureInstaller()
            installer.start(self._sdk(temp), "nvapi-test-key", platform="win32", popen=popen)
            installer._thread.join(timeout=2)
            self.assertEqual(captured["env"]["NGC_CLI_API_KEY"], "nvapi-test-key")
            self.assertIn("-features", captured["args"])
            self.assertEqual(captured["args"][-1], ",".join(REQUIRED_FEATURES))
            status = installer.status()
            self.assertFalse(status["running"])
            self.assertEqual(status["returncode"], 0)
            self.assertNotIn("nvapi-test-key", str(status))

    def test_rejects_missing_key_and_missing_installer(self):
        installer = FeatureInstaller()
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                installer.start(temp, "", platform="win32", popen=lambda *_a, **_k: None)
            with self.assertRaises(FileNotFoundError):
                installer.start(temp, "nvapi-test-key", platform="win32", popen=lambda *_a, **_k: None)

    def test_rejects_non_windows(self):
        with self.assertRaises(RuntimeError):
            FeatureInstaller().start("unused", "nvapi-test-key", platform="linux")


if __name__ == "__main__":
    unittest.main()
