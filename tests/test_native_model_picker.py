import ast
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

class NativePickerTests(unittest.TestCase):
    def test_format_directories_and_cancel(self):
        tree=ast.parse(Path('desktop.py').read_text(encoding='utf-8'))
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='import_model_package')
        scope={'Path':Path,'webview':types.SimpleNamespace(FileDialog=types.SimpleNamespace(OPEN='file',FOLDER='folder'))}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'picker','exec'),scope)
        with tempfile.TemporaryDirectory() as folder:
            calls=[]
            win=types.SimpleNamespace(create_file_dialog=lambda *a,**kw:calls.append((a,kw)))
            obj=types.SimpleNamespace(holder={'window':win,'library_mode':True})
            with patch('config.MODELS_DIR',Path(folder)):
                for kind in ['pmx','vrm','live2d']:
                    self.assertEqual(scope['import_model_package'](obj,kind),{'cancelled':True})
                    self.assertEqual(calls[-1][1]['directory'],str(Path(folder)/kind))
                    self.assertEqual(calls[-1][0][0],'file' if kind=='vrm' else 'folder')
                obj.holder['library_mode']=False
                self.assertIn('error',scope['import_model_package'](obj,'pmx'))
