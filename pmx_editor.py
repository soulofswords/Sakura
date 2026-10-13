"""Open an installed PMX Editor with a selected local model."""
from pathlib import Path
import subprocess
import os

BASE = Path(__file__).resolve().parent
MODELS = BASE / 'models'
EDITOR = BASE / 'tools' / 'pmx-editor' / 'PmxEditor.exe'

def model_file(relative_path):
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError('Select a PMX model first.')
    file = (MODELS / relative_path).resolve()
    if not file.is_relative_to(MODELS.resolve()) or file.suffix.lower() != '.pmx' or not file.is_file():
        raise ValueError('Choose an existing PMX file inside Sakura’s models folder.')
    return file

def find_editor(configured_path=None):
    for candidate in ([Path(configured_path)] if configured_path else []) + [EDITOR]:
        if candidate.name.lower() == 'pmxeditor.exe' and candidate.is_file():
            return candidate.resolve()
    return None

def open_model(relative_path, editor_path=None):
    file = model_file(relative_path)
    if os.name != 'nt':
        raise RuntimeError('PMX Editor is Windows-only. PMX models still render here; edit them on Windows and reload the model.')
    editor = find_editor(editor_path)
    if editor is None:
        raise RuntimeError('PMX Editor is missing. Select your PmxEditor.exe installation.')
    subprocess.Popen([str(editor), str(file)], cwd=str(editor.parent),
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    return {'opened': True, 'model': relative_path}
