"""Refresh only cloud-library additions in existing development app copies.

Keeps all other edition-specific Python, renderer and UI changes intact.
Does not restart running apps or build a release installer.
"""
from pathlib import Path
import shutil

SOURCE = Path(__file__).resolve().parents[1]
ROUTE = "from model_library import router as model_library_router\napp.include_router(model_library_router(MODELS_DIR, _started_locally))"
RESET_ROUTE = "from model_library_confirm import router as model_library_confirm_router\napp.include_router(model_library_confirm_router(_served_locally, _started_locally))"
LOCAL_ROUTE = "from local_model_library import router as local_model_library_router\napp.include_router(local_model_library_router(MODELS_DIR, _started_locally))"
SCRIPT = '    <script type="module" src="/static/js/model-library.js?v=variants7"></script>'


def sync(destination):
    app = destination / 'app.py'
    html = destination / 'static/index.html'
    if not app.is_file() or not html.is_file():
        raise ValueError('This is not an editable Sakura app copy: ' + str(destination))
    code = app.read_text(encoding='utf-8')
    markup = html.read_text(encoding='utf-8')
    marker = '\nif __name__ == "__main__":'
    for route in (ROUTE, RESET_ROUTE, LOCAL_ROUTE):
        if route in code:
            continue
        if route.splitlines()[0] in code:
            raise ValueError('Existing library wiring differs; review it before syncing ' + str(destination))
        if marker not in code or 'def _started_locally(' not in code or 'def _served_locally(' not in code:
            raise ValueError('Cannot safely attach the library routes in ' + str(destination))
        code = code.replace(marker, '\n' + route + '\n' + marker, 1)
    import re
    if '/static/js/model-library.js' in markup:
        markup = re.sub(r'<script type="module" src="/static/js/model-library\.js\?v=[^"]+"></script>', SCRIPT.strip(), markup)
    else:
        if '</body>' not in markup:
            raise ValueError('Cannot find the application script section.')
        markup = markup.replace('</body>', SCRIPT + '\n</body>', 1)
    local_script='    <script type="module" src="/static/js/local-character-library.js?v=1"></script>'
    if '/static/js/local-character-library.js' not in markup:
        markup=markup.replace('</body>',local_script+'\n</body>',1)
    for name in ('model_library.py', 'model_library_confirm.py', 'model_library_config.py', 'model_library_previews.py',
                 'local_model_library.py','static/js/model-library.js','static/js/local-character-library.js','static/model-library-preview.html'):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / name, target)
    app.write_text(code, encoding='utf-8')
    html.write_text(markup, encoding='utf-8')
    print('Cloud library synced:', destination)


if __name__ == '__main__':
    for edition in ('Sakura Companion', 'Sakura VTuber'):
        sync(SOURCE.parent / edition / 'Sakura')
