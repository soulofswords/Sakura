"""Check native drag dispatch without opening a window or starting AI services."""
import ast
import sys
import types
from pathlib import Path
from unittest.mock import patch

source = ast.parse(Path('desktop.py').read_text(encoding='utf-8'))
function = next(node for node in ast.walk(source) if isinstance(node, ast.FunctionDef) and node.name == 'update_hair_drag')
scripts = []
position = [0, 0]
mouse = [1]
page = types.SimpleNamespace(runJavaScript=scripts.append)
native = types.SimpleNamespace(x=lambda: position[0], y=lambda: position[1], webview=types.SimpleNamespace(page=lambda: page))
holder = {'library_mode': False}
context = {'native': native, 'holder': holder, 'drag_position': [0, 0], 'Qt': types.SimpleNamespace(MouseButton=types.SimpleNamespace(LeftButton=1))}
qtwidgets = types.ModuleType('PySide6.QtWidgets')
qtwidgets.QApplication = types.SimpleNamespace(mouseButtons=lambda: mouse[0])
exec(compile(ast.Module(body=[function], type_ignores=[]), 'desktop.py', 'exec'), context)
with patch.dict(sys.modules, {'PySide6.QtWidgets': qtwidgets}):
    tick = context['update_hair_drag']
    tick(); assert not scripts
    position[:] = [10, 8]; tick(); assert 'dx:10,dy:8' in scripts[-1]
    mouse[0] = 0; position[:] = [30, 20]; tick(); assert len(scripts) == 1
    mouse[0] = 1; position[:] = [35, 25]; tick(); assert 'dx:5,dy:5' in scripts[-1]
    holder['library_mode'] = True; position[:] = [45, 25]; tick(); assert len(scripts) == 2
    holder['library_mode'] = False; position[:] = [1000, 25]; tick(); assert len(scripts) == 2
print('PASS: native flower drag dispatch, no stationary/passive/library/geometry-jump impulses')
