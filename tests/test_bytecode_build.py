import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('bytecode_builder', Path(__file__).resolve().parents[1] / 'tools/build_bytecode.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BytecodeTests(unittest.TestCase):
    def test_checked_cache_runs_and_invalidates_after_source_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'example.py'
            source.write_text('value = 12\nassert value > 0\n')
            before = source.read_bytes()
            records = builder.compile_application(root, root)
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(len(records), 1)
            run = lambda: subprocess.check_output([sys.executable, '-c', 'import example; print(example.value, example.__cached__)'], cwd=root, text=True)
            self.assertTrue(run().startswith('12 '))
            source.write_text('value = 24\nassert value > 0\n')
            self.assertTrue(run().startswith('24 '))
            builder.compile_application(root, root)
            first = records[0][0].read_bytes()
            builder.compile_application(root, root)
            self.assertEqual(records[0][0].read_bytes(), first)

    def test_invalid_source_fails_compilation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'invalid.py').write_text('def broken(:\n')
            with self.assertRaises(Exception):
                builder.compile_application(root / 'compiled', root)

    def test_assertions_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'example.py').write_text('assert False, "assertions enabled"\n')
            builder.compile_application(root, root)
            result = subprocess.run([sys.executable, '-c', 'import example'], cwd=root, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('assertions enabled', result.stderr)


if __name__ == '__main__':
    unittest.main()
