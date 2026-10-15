import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from mobile_models import bundle_model,bundle_selected_folder

class MobileModelTests(unittest.TestCase):
    def test_explicit_folder_transfer_keeps_every_file_and_nested_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)/'Chosen';(folder/'nested').mkdir(parents=True)
            source=folder/'nested/model.pmx';source.write_bytes(b'pmx')
            (folder/'extra.custom').write_bytes(b'whole folder means custom files too')
            (folder/'nested/face.png').write_bytes(b'png')
            metadata,archive=bundle_selected_folder(source,folder,'pmx',Path(directory)/'cache')
            self.assertEqual(metadata['entry'],'nested/model.pmx')
            with zipfile.ZipFile(archive) as zipped:
                self.assertEqual(set(zipped.namelist()),{'nested/model.pmx','nested/face.png','extra.custom','sakura-mobile-model.json'})
                self.assertEqual(json.loads(zipped.read('sakura-mobile-model.json'))['entry'],'nested/model.pmx')

    def test_explicit_vrm_transfer_keeps_only_selected_file(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'model.vrm';source.write_bytes(b'vrm');(source.parent/'other.vrm').write_bytes(b'other')
            _,archive=bundle_selected_folder(source,source,'vrm',Path(directory)/'cache')
            with zipfile.ZipFile(archive) as zipped:self.assertEqual(set(zipped.namelist()),{'model.vrm','sakura-mobile-model.json'})

    def test_transfer_contains_selected_model_assets_and_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'models';folder=root/'Japanese hair';folder.mkdir(parents=True)
            (folder/'テスト.pmx').write_bytes(b'model')
            (folder/'textures').mkdir();(folder/'textures/skin.png').write_bytes(b'png')
            (folder/'private.key').write_bytes(b'not a model asset')
            metadata,archive=bundle_model('/models/Japanese%20hair/%E3%83%86%E3%82%B9%E3%83%88.pmx',root,Path(directory)/'cache')
            self.assertEqual(metadata['sha256'],hashlib.sha256(archive.read_bytes()).hexdigest())
            with zipfile.ZipFile(archive) as zipped:
                self.assertEqual(set(zipped.namelist()),{'テスト.pmx','textures/skin.png','sakura-mobile-model.json'})
                self.assertEqual(json.loads(zipped.read('sakura-mobile-model.json'))['format'],'pmx')

    def test_rejects_external_urls_traversal_missing_and_unsupported(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'models';root.mkdir();(Path(directory)/'secret.pmx').write_bytes(b'secret');(root/'notes.txt').write_text('not a model')
            for url in ['https://example.com/models/a.pmx','/models/../secret.pmx','/models/%2e%2e/secret.pmx','/models/missing.vrm','/models/notes.txt']:
                with self.subTest(url=url),self.assertRaises(ValueError):bundle_model(url,root,Path(directory)/'cache')

    def test_vrm_does_not_include_neighboring_models(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'models';root.mkdir();(root/'one.vrm').write_bytes(b'one');(root/'two.vrm').write_bytes(b'two');(root/'settings.json').write_text('{}')
            metadata,archive=bundle_model('/models/one.vrm',root,Path(directory)/'cache')
            with zipfile.ZipFile(archive) as zipped:self.assertEqual(set(zipped.namelist()),{'one.vrm','sakura-mobile-model.json'})
            self.assertEqual(metadata['entry'],'one.vrm')
