import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import zipfile
import tarfile
import hashlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import local_model_setup as setup

class SetupTests(unittest.TestCase):
    def test_native_model_is_detected_without_starting_or_downloading(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);local=root/'desktop-profile/agent-local-ai';local.mkdir(parents=True)
            (root/'settings.json').write_text(json.dumps({'ollama_model':'sakura-native:existing'}))
            weights=root/'model.gguf';weights.write_bytes(b'GGUFweights')
            entry={'path':str(weights),'projector':False,'engine':'llama.cpp'}
            (local/'models.json').write_text(json.dumps({'existing':entry}))
            binary=local/'runtime-cuda/llama-server.exe';binary.parent.mkdir();binary.write_bytes(b'runtime')
            with patch.object(setup.requests,'post') as post,patch.object(setup.requests,'get') as get:
                self.assertTrue(setup.installed(root))
                weights.unlink();self.assertFalse(setup.installed(root))
                post.assert_not_called();get.assert_not_called()

    def test_existing_colibri_requires_its_runtime_and_valid_container(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);local=root/'desktop-profile/agent-local-ai';local.mkdir(parents=True)
            (root/'settings.json').write_text(json.dumps({'ollama_model':'sakura-native:existing'}))
            (local/'models.json').write_text(json.dumps({'existing':{'path':str(root/'weights'),'engine':'colibri','projector':False}}))
            binary=local/'colibri-runtime/coli';binary.parent.mkdir();binary.write_bytes(b'runtime')
            with patch('inference_engines.colibri_model',return_value=(root/'weights',100,False)) as inspect:
                self.assertTrue(setup.installed(root));inspect.assert_called_once()
            with patch('inference_engines.colibri_model',side_effect=ValueError('Incomplete model')):
                self.assertFalse(setup.installed(root))
            binary.unlink();self.assertFalse(setup.installed(root))

    def test_archive_traversal_rejected_before_extract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root/'runtime.zip'
            with zipfile.ZipFile(archive,'w') as output:
                output.writestr('valid.txt','okay')
                output.writestr('../escape.txt','bad')
            with self.assertRaises(ValueError):setup.extract(archive,root/'out')
            self.assertFalse((root/'out/valid.txt').exists())
            self.assertFalse((root/'escape.txt').exists())

    def test_installed_requires_all_blob_files_and_sizes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            runtime=root/'ollama-runtime'/('ollama.exe' if sys.platform=='win32' else 'bin/ollama')
            runtime.parent.mkdir(parents=True);runtime.write_bytes(b'fixture')
            manifest=root/'llm-models/manifests/registry.ollama.ai/library/qwen3-vl/2b-instruct'
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({'config':{'digest':'sha256:abc','size':3},'layers':[{'digest':'sha256:def','size':4}]}))
            self.assertFalse(setup.installed(root))
            blobs=root/'llm-models/blobs';blobs.mkdir()
            (blobs/'sha256-abc').write_bytes(b'abc');(blobs/'sha256-def').write_bytes(b'wrong')
            self.assertFalse(setup.installed(root))
            (blobs/'sha256-def').write_bytes(b'defg')
            self.assertTrue(setup.installed(root))

    def run_pull(self,lines,expected_error=False,choice='2b',vision=True):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);settings=root/'settings.json'
            original={'llm_provider':'gemini','user_title':'Master','selected_model':'models/miku.pmx'}
            settings.write_text(json.dumps(original))
            pull=MagicMock();pull.__enter__.return_value=pull
            pull.iter_lines.return_value=[json.dumps(line).encode() for line in lines]
            show=MagicMock()
            show.json.return_value={'capabilities':['completion','vision'] if vision else ['completion']}
            with patch.object(setup,'ensure_runtime'),patch.object(setup.shutil,'disk_usage',return_value=MagicMock(free=80*1024**3)),patch.object(setup.requests,'post',side_effect=[pull,show]) as request,patch('ollama_runtime.server_for_folder',return_value='http://127.0.0.1:11435'),patch('ollama_runtime.stop') as stop,patch.object(setup,'progress'):
                if expected_error:
                    with self.assertRaises(RuntimeError):setup.install(choice,root)
                    self.assertEqual(json.loads(settings.read_text()),original)
                else:
                    setup.install(choice,root)
                    result=json.loads(settings.read_text());self.assertEqual(result['llm_provider'],'ollama')
                    self.assertEqual(result['ollama_model'],setup.MODELS[choice]);self.assertEqual(result['ollama_context'],2048 if choice=='2b' else 4096)
                    self.assertEqual(result['ollama_vision_model'],setup.MODELS[choice])
                    self.assertEqual(request.call_args_list[0].kwargs['json']['model'],setup.MODELS[choice])
                    self.assertEqual(result['selected_model'],original['selected_model'])
                    self.assertTrue((root/'llm-models/manifests').is_dir())
                    self.assertEqual(request.call_count,2)
                stop.assert_called_once()
    def test_success_only_changes_provider_after_verified_download(self):self.run_pull([{'status':'success'}])
    def test_download_error_preserves_gemini_and_stops_owned_server(self):self.run_pull([{'error':'quota'}],True)
    def test_empty_or_partial_download_preserves_settings(self):self.run_pull([{'status':'pulling manifest'}],True)
    def test_model_catalog_is_consistent_with_windows_selectors(self):
        root=Path(__file__).resolve().parents[1]
        dialog=(root/'launcher/LocalModelDialog.cs').read_text(encoding='utf-8')
        installer=(root/'launcher/Installer.cs').read_text(encoding='utf-8')
        self.assertEqual(setup.MODEL_OPTIONS[2][1], 'qwen3.8:27b')
        for key, tag, label, ram, vram, disk, download in setup.MODEL_OPTIONS:
            self.assertIn('"'+key+'"',dialog)
            self.assertIn('"'+key+'"',installer)
            self.assertGreaterEqual(disk,8)
        self.assertGreaterEqual(setup.MODEL_OPTIONS[2][4],24)

    def test_large_model_checks_disk_before_starting_runtime(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(setup.shutil,'disk_usage',return_value=MagicMock(free=12*1024**3)), patch.object(setup,'ensure_runtime') as runtime:
            with self.assertRaises(RuntimeError):setup.install('qwen38-27b',Path(directory))
            runtime.assert_not_called()

    def test_gemma_and_large_qwen_use_the_selected_model_for_vision(self):
        for choice in ('gemma3-4b','qwen38-27b','qwen35-9b'):
            with self.subTest(choice=choice):self.run_pull([{'status':'success'}],choice=choice)

    def test_download_without_vision_preserves_previous_settings(self):
        self.run_pull([{'status':'success'}],expected_error=True,vision=False)

    def test_only_allowlisted_models(self):
        with self.assertRaises(ValueError):setup.install('llama')
    def test_checksum_mismatch_cannot_install_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            response=MagicMock();response.__enter__.return_value=response
            response.headers={'Content-Length':'3'};response.iter_content.return_value=[b'bad']
            with patch.object(setup.requests,'get',return_value=response),patch.object(setup,'progress'):
                with self.assertRaises(RuntimeError):setup.ensure_runtime(Path(directory))
            self.assertFalse((Path(directory)/'ollama-runtime').exists())
            self.assertEqual(list((Path(directory)/'downloads').iterdir()),[])

    def test_mac_flat_runtime_keeps_libraries_next_to_executable(self):
        archive=io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w:gz') as writer:
            for name,data in [('ollama',b'executable'),('libggml.dylib',b'library')]:
                entry=tarfile.TarInfo(name);entry.size=len(data);writer.addfile(entry,io.BytesIO(data))
        payload=archive.getvalue();response=MagicMock();response.__enter__.return_value=response
        response.headers={'Content-Length':str(len(payload))};response.iter_content.return_value=[payload]
        with tempfile.TemporaryDirectory() as directory,patch.object(setup.sys,'platform','darwin'),patch.dict(setup.RUNTIMES,{'darwin':('fixture.tgz',hashlib.sha256(payload).hexdigest())}),patch.object(setup.requests,'get',return_value=response),patch.object(setup,'progress'):
            setup.ensure_runtime(Path(directory))
            self.assertEqual((Path(directory)/'ollama-runtime/bin/ollama').read_bytes(),b'executable')
            self.assertEqual((Path(directory)/'ollama-runtime/bin/libggml.dylib').read_bytes(),b'library')

    def test_tar_link_outside_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);archive=root/'runtime.tgz'
            with tarfile.open(archive,'w:gz') as writer:
                link=tarfile.TarInfo('library');link.type=tarfile.SYMTYPE;link.linkname='../outside'
                writer.addfile(link)
            with self.assertRaises(ValueError):setup.extract(archive,root/'out')

if __name__=='__main__':unittest.main()
