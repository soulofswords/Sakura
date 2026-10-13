import unittest
import tempfile
import ast
import types
from pathlib import Path
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

    def test_configured_editor_and_missing_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            configured=folder/'PmxEditor.exe';configured.touch()
            with patch.object(pmx_editor,'EDITOR',folder/'missing.exe'):
                self.assertEqual(pmx_editor.find_editor(str(configured)),configured.resolve())
                self.assertIsNone(pmx_editor.find_editor(str(folder/'other.exe')))
                self.assertIsNone(pmx_editor.find_editor())

    def test_configured_editor_is_used(self):
        with tempfile.TemporaryDirectory() as directory:
            editor=Path(directory)/'PmxEditor.exe';editor.touch()
            with patch.object(pmx_editor,'model_file',return_value=Path(directory)/'model.pmx'),patch('pmx_editor.subprocess.Popen') as spawn:
                pmx_editor.open_model('pmx/model.pmx',str(editor))
                self.assertEqual(spawn.call_args.args[0][0],str(editor.resolve()))
                self.assertEqual(spawn.call_args.kwargs['cwd'],str(editor.parent))

    def test_native_picker_cancel_and_saved_selection(self):
        tree=ast.parse(Path('desktop.py').read_text(encoding='utf-8'))
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='open_pmx_editor')
        scope={'sys':types.SimpleNamespace(platform='win32'),'get_settings':lambda:{},
               'webview':types.SimpleNamespace(FileDialog=types.SimpleNamespace(OPEN='open'))}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'editor-picker','exec'),scope)
        with tempfile.TemporaryDirectory() as directory:
            editor=Path(directory)/'PmxEditor.exe';editor.touch()
            window=types.SimpleNamespace(create_file_dialog=lambda *args,**kwargs:None)
            owner=types.SimpleNamespace(holder={'window':window})
            with patch.object(pmx_editor,'model_file'),patch.object(pmx_editor,'EDITOR',Path(directory)/'missing.exe'),patch.object(pmx_editor,'open_model') as opened,patch.dict('sys.modules',{'app':types.SimpleNamespace(save_settings=lambda data:saved.append(data))}):
                saved=[]
                self.assertEqual(scope['open_pmx_editor'](owner,'pmx/model.pmx'),{'cancelled':True})
                opened.assert_not_called()
                window.create_file_dialog=lambda *args,**kwargs:[str(editor)]
                scope['open_pmx_editor'](owner,'pmx/model.pmx')
                self.assertEqual(saved,[{'pmx_editor_path':str(editor.resolve())}])
                opened.assert_called_once_with('pmx/model.pmx',str(editor.resolve()))
