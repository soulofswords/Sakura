import ast
import base64
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw

class ScreenSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree=ast.parse((Path(__file__).parents[1]/'desktop.py').read_text(encoding='utf-8'))
        method=next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='screen_snapshot')
        module=ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[]));namespace={}
        exec(compile(module,'desktop.py','exec'),namespace)
        cls.capture=staticmethod(namespace['screen_snapshot'])

    def test_screen_permission_required(self):
        with patch('PIL.ImageGrab.grab') as grab:
            self.assertIsNone(self.capture(SimpleNamespace(screen_access=False)))
            grab.assert_not_called()

    def test_visible_screen_is_not_masked_by_maximized_companion(self):
        screen=Image.new('RGB',(1920,1080),(190,220,240))
        ImageDraw.Draw(screen).rectangle((600,200,1300,800),fill=(230,90,70))
        with patch('PIL.ImageGrab.grab',return_value=screen) as grab:
            encoded=self.capture(SimpleNamespace(screen_access=True))
        captured=Image.open(io.BytesIO(base64.b64decode(encoded)))
        self.assertEqual(captured.size,(1600,900))
        self.assertGreater(captured.getpixel((800,450))[0],180)
        self.assertGreater(captured.getpixel((100,100))[1],180)
        grab.assert_called_once()

if __name__=='__main__':unittest.main()
