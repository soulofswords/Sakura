"""Release identity is stored separately from editable user preferences."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
VERSION='1.0.2'
try:
    EDITION=json.loads((ROOT/'product.json').read_text(encoding='utf-8')).get('edition','combined')
except (OSError,ValueError,AttributeError):
    EDITION='combined'
if EDITION not in ('combined','companion','vtuber'):EDITION='combined'
DISPLAY_NAME='Sakura VTuber' if EDITION=='vtuber' else 'Sakura Companion'
LAUNCHER_NAME=DISPLAY_NAME+'.exe' if EDITION!='combined' else 'Desktop Companion.exe'
INSTALLATION_ID=hashlib.sha256(str(ROOT).casefold().encode()).hexdigest()[:16]
