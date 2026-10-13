import unittest
from unittest.mock import patch
import pmx_editor

class EditorTests(unittest.TestCase):
    def test_existing_model_passed_as_single_argument(self):
        path = 'pmx/Miku universe/Miku/Miku-Elegant Princess/Miku-Elegant Princess.pmx'
        with patch('pmx_editor.subprocess.Popen') as spawn:
            self.assertTrue(pmx_editor.open_model(path)['opened'])
            command = spawn.call_args.args[0]
            self.assertEqual(len(command), 2)
            self.assertEqual(command[1], str(pmx_editor.model_file(path)))
            self.assertEqual(spawn.call_args.kwargs['cwd'], str(pmx_editor.EDITOR.parent))

    def test_invalid_paths_rejected(self):
        for path in ['../../desktop.py', 'vrm/nonexistent.vrm', '', '../tools/pmx-editor/PmxEditor.exe']:
            with self.assertRaises(ValueError):
                pmx_editor.model_file(path)
