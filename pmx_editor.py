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

def open_model(relative_path):
    file = model_file(relative_path)
    if os.name != 'nt':
        raise RuntimeError('PMX Editor is Windows-only. PMX models still render here; edit them on Windows and reload the model.')
    if not EDITOR.is_file():
        raise RuntimeError('PMX Editor is missing from Sakura/tools/pmx-editor.')
    subprocess.Popen([str(EDITOR), str(file)], cwd=str(EDITOR.parent),
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    return {'opened': True, 'model': relative_path}
