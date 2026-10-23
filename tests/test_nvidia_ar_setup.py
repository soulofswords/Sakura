import tempfile
from pathlib import Path
import unittest
from nvidia_ar_setup import sdk_status, import_sdk_archive
import io
import zipfile

class OptionalSdkTests(unittest.TestCase):
    def test_archive_import_does_not_claim_tracking_is_ready(self):
        package=io.BytesIO()
        with zipfile.ZipFile(package,'w') as archive:
            archive.writestr('ARSDK/bin/nvARPose.dll',b'fixture')
        package.seek(0)
        with tempfile.TemporaryDirectory() as tmp:
            result=import_sdk_archive(package,tmp)
            self.assertTrue(result['installed'])
            self.assertFalse(result['tracking_ready'])
            self.assertTrue(Path(result['folder']).is_relative_to(Path(tmp)))

    def test_archive_traversal_is_rejected_before_extraction(self):
        package=io.BytesIO()
        with zipfile.ZipFile(package,'w') as archive:
            archive.writestr('nvARPose.dll',b'fixture')
            archive.writestr('../escaped.txt',b'unsafe')
        package.seek(0)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                import_sdk_archive(package,tmp)
            self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_unrelated_zip_is_rejected(self):
        package=io.BytesIO()
        with zipfile.ZipFile(package,'w') as archive:
            archive.writestr('unrelated.txt',b'fixture')
        package.seek(0)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                import_sdk_archive(package,tmp)
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

    def test_complete_nested_sdk_is_ready_for_direct_tracking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'sdk-package'/'ARSDK';(root/'bin/models').mkdir(parents=True)
            (root/'bin/nvARPose.dll').write_bytes(b'fixture')
            for feature,dll in [('nvarfaceexpressions','nvARFaceExpressions.dll'),('nvarlandmarkdetection','nvARLandmarkDetection.dll'),('nvarfaceboxdetection','nvARFaceBoxDetection.dll')]:
                folder=root/'features'/feature/'bin';folder.mkdir(parents=True);(folder/dll).write_bytes(b'fixture')
            for model in ('face_expressions_fp16_mlp_86.engine.trtpkg','face_and_landmark_detector_119_fp32_86.engine.trtpkg','face_detection_86.engine.trtpkg'):
                (root/'bin/models'/model).write_bytes(b'fixture')
            result=sdk_status(str(Path(tmp)/'sdk-package'),platform='win32')
            self.assertTrue(result['tracking_ready'])
            self.assertEqual(Path(result['folder']),root)
