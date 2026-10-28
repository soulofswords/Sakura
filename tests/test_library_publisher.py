import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

source=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('library_publisher',source/'tools/publish-model-library.py')
publisher=importlib.util.module_from_spec(spec);spec.loader.exec_module(publisher)


class PublisherTests(unittest.TestCase):
    def test_missing_descriptor_is_rebuilt_only_for_one_unambiguous_moc_and_texture_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'character.moc3').write_bytes(b'MOC3')
            (root/'character.8192').mkdir();(root/'character.8192/texture_00.png').write_bytes(b'png')
            (root/'smile.exp3.json').write_text('{}')
            publisher.complete_descriptor(root)
            data=json.loads((root/'character.model3.json').read_text())
            self.assertEqual(data['FileReferences']['Textures'],['character.8192/texture_00.png'])
            self.assertEqual(data['FileReferences']['Expressions'][0]['File'],'smile.exp3.json')
            self.assertEqual(data['FileReferences']['Moc'],'character.moc3')

    def test_conflicting_duplicate_assets_are_not_silently_selected(self):
        with tempfile.TemporaryDirectory() as folder:
            drive=publisher.Drive({})
            drive.children=Mock(return_value=[{'id':'one','name':'texture.png','mimeType':'image/png','size':'3','md5Checksum':'one'},
                                              {'id':'two','name':'texture.png','mimeType':'image/png','size':'3','md5Checksum':'two'}])
            response=Mock(status_code=200);response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
            response.iter_content.return_value=[b'png'];drive.session.get=Mock(return_value=response)
            with self.assertRaisesRegex(ValueError,'conflicting duplicate'):drive.download_tree('folder',Path(folder))

    def test_identical_duplicate_texture_is_downloaded_once(self):
        with tempfile.TemporaryDirectory() as folder:
            drive=publisher.Drive({});entry={'id':'one','name':'texture.png','mimeType':'image/png','size':'3','md5Checksum':'same'}
            drive.children=Mock(return_value=[entry,{**entry,'id':'two'}])
            response=Mock(status_code=200);response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
            response.iter_content.return_value=[b'png'];drive.session.get=Mock(return_value=response)
            drive.download_tree('folder',Path(folder));drive.session.get.assert_called_once()

    def test_new_drive_folder_is_discovered_on_next_pass_without_repreparing_existing_model(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);credentials=root/'private.json';credentials.write_text(json.dumps({'client_id':'id','client_secret':'secret','refresh_token':'refresh'}))
            output=root/'packages';output.mkdir()
            old='live2d-'+hashlib.sha256(b'old').hexdigest()[:24]
            record={'id':old,'name':'Old','format':'live2d','bytes':3,'sha256':'a'*64,'version':'1'}
            (output/(old+'.zip')).write_bytes(b'old');(output/'prepared-models.json').write_text(json.dumps({old:record}))
            drive=Mock();drive.children.return_value=[{'id':'old','name':'Old','mimeType':'application/vnd.google-apps.folder'},
                                                      {'id':'new','name':'New','mimeType':'application/vnd.google-apps.folder'}]
            def package(stage,name,identifier,destination):
                (destination/(identifier+'.zip')).write_bytes(b'new')
                return {**record,'id':identifier,'name':name}
            with patch('sys.argv',['publisher','--workspace-credentials',str(credentials),'--output',str(output),'--workers','1']), \
                 patch.object(publisher.requests,'post',return_value=Mock(status_code=200,json=lambda:{'access_token':'test'})), \
                 patch.object(publisher,'Drive',return_value=drive),patch.object(publisher,'package_folder',side_effect=package) as prepare:
                self.assertEqual(publisher.main(),0)
            prepare.assert_called_once();self.assertEqual(prepare.call_args.args[1],'New')
            self.assertEqual(len(json.loads((output/'catalogue.json').read_text())['models']),2)
