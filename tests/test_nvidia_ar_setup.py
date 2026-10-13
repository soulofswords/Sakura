import tempfile
from pathlib import Path
import unittest
from nvidia_ar_setup import sdk_status

class OptionalSdkTests(unittest.TestCase):
    def test_missing_sdk_is_never_downloaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing=Path(tmp)/'absent';result=sdk_status(str(missing),platform='win32')
            self.assertFalse(missing.exists());self.assertFalse(result['installed']);self.assertFalse(result['tracking_ready'])
    def test_core_and_features_are_reported_without_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'nvARPose.dll').write_bytes(b'fixture')
            folder=root/'features/nvARFaceExpressions';folder.mkdir(parents=True);(folder/'feature.dll').write_bytes(b'fixture')
            result=sdk_status(str(root),platform='win32');self.assertTrue(result['installed']);self.assertTrue(result['features']['nvarfaceexpressions']);self.assertFalse(result['features']['nvarlandmarkdetection']);self.assertFalse(result['tracking_ready'])
            self.assertFalse(sdk_status(str(root),platform='darwin')['platform_supported'])
