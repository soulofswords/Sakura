"""Exercise the real Windows decoder on an intact and corrupted package."""
import importlib.util
import json
import lzma
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

BASE=Path(__file__).resolve().parents[1]


@unittest.skipUnless(Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe').exists(),'Windows installer test')
class InstallerCompressionTests(unittest.TestCase):
    def test_offline_roundtrip_update_and_corruption(self):
        spec=importlib.util.spec_from_file_location('installer_builder',BASE/'tools/build-installers.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory(prefix='sakura-compression-') as folder:
            root=Path(folder);archive=root/'payload.zip';compressed=root/'payload.xz'
            with zipfile.ZipFile(archive,'w') as output:
                output.writestr('Sakura/settings.json',json.dumps({'preserve_configuration_on_reinstall':True,'physics_mode':'normal'}))
                output.writestr('Sakura/example.bin',b'complete runtime data\0'*10000)
            compressed.write_bytes(lzma.compress(archive.read_bytes()))
            bootstrap=BASE/'tools/packaging-cache/python-3.12.10-embed-amd64.zip'
            exe=root/'Setup.exe';builder.compile_cs(exe,['Installer.cs'],['System.IO.Compression','System.IO.Compression.FileSystem','System.Web.Extensions'],compressed,bootstrap)
            install=root/'installed'
            subprocess.run([str(exe),'--test-install',str(install)],check=True)
            self.assertEqual((install/'Sakura/example.bin').read_bytes(),b'complete runtime data\0'*10000)
            settings=install/'Sakura/settings.json';settings.write_text(json.dumps({'preserve_configuration_on_reinstall':True,'physics_mode':'off','custom':'retained'}))
            subprocess.run([str(exe),'--test-install',str(install)],check=True)
            self.assertEqual(json.loads(settings.read_text())['custom'],'retained')
            compressed.write_bytes(b'corrupt payload')
            builder.compile_cs(exe,['Installer.cs'],['System.IO.Compression','System.IO.Compression.FileSystem','System.Web.Extensions'],compressed,bootstrap)
            self.assertNotEqual(subprocess.run([str(exe),'--test-install',str(install)]).returncode,0)
            self.assertEqual((install/'Sakura/example.bin').read_bytes(),b'complete runtime data\0'*10000)
