import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
import hashlib
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('windows_builder',Path(__file__).resolve().parents[1]/'tools/build-windows-release.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class BuilderTests(unittest.TestCase):
    def test_failed_build_logs_markdown_and_preserves_published_exe(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);exe=root/'Sakura-Setup-Windows-x64.exe';exe.write_bytes(b'last good release')
            (root/'tools').mkdir()
            with patch.object(builder,'BASE',root),patch.object(builder.Release,'build',side_effect=RuntimeError('synthetic compiler failure')),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(builder.main(['--output',str(root)]),1)
            self.assertEqual(exe.read_bytes(),b'last good release')
            self.assertIn('synthetic compiler failure',(root/'Build-Errors.md').read_text())
            self.assertEqual(len(list((root/'build-reports').glob('Errors-*.md'))),1)
    def test_child_failure_and_unicode_output_are_logged(self):
        with tempfile.TemporaryDirectory() as directory,contextlib.redirect_stdout(io.StringIO()):
            release=builder.Release(Path(directory))
            with self.assertRaises(RuntimeError):release.run('Broken test',[sys.executable,'-c',"print('Test Ω'); raise SystemExit(3)"])
            self.assertIn('Test Ω',release.log.read_text(encoding='utf-8'))
    def test_non_executable_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            fake=Path(directory)/'fake.exe';fake.write_bytes(b'not an exe')
            with self.assertRaises(ValueError):builder.pe_check(fake)
    def test_source_snapshot_detects_changes(self):
        with tempfile.TemporaryDirectory() as directory,contextlib.redirect_stdout(io.StringIO()):
            root=Path(directory)
            (root/'tools').mkdir();(root/'launcher').mkdir();(root/'tests').mkdir()
            code=root/'model.py';code.write_text('first version')
            (root/'tools/build-installers.py').write_text('from pathlib import Path\ndef app_files():\n yield Path(__file__).parents[1]/"model.py", "Sakura/model.py"\n')
            release=builder.Release(root/'out')
            with patch.object(builder,'BASE',root):
                before=release.source_snapshot();code.write_text('updated version')
                self.assertNotEqual(before,release.source_snapshot())
    def test_publisher_copies_before_atomic_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.exe';destination=root/'published.exe'
            source.write_bytes(b'new release');destination.write_bytes(b'old release')
            builder.publish(source,destination,hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(destination.read_bytes(),b'new release')
            self.assertTrue(source.exists())
            self.assertEqual(list(root.glob('*.building-*')),[])
    def test_failed_publication_does_not_replace_good_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.exe';destination=root/'published.exe'
            source.write_bytes(b'new release');destination.write_bytes(b'old release')
            with self.assertRaises(RuntimeError):builder.publish(source,destination,'incorrect checksum')
            self.assertEqual(destination.read_bytes(),b'old release')
            self.assertEqual(list(root.glob('*.building-*')),[])

if __name__=='__main__':unittest.main()
