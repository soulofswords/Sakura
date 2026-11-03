"""Release identity is stored separately from editable user preferences."""
import hashlib
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parent
VERSION='2.0'
try:
    metadata=json.loads((ROOT/'product.json').read_text(encoding='utf-8'))
    EDITION=metadata.get('edition','combined')
    if isinstance(metadata.get('version'),str) and re.fullmatch(r'\d+\.\d+(?:\.\d+)?',metadata['version']):
        VERSION=metadata['version']
except (OSError,ValueError,AttributeError):
    EDITION='combined'
if EDITION not in ('combined','companion','vtuber'):EDITION='combined'
DISPLAY_NAME='Sakura VTuber' if EDITION=='vtuber' else 'Sakura Companion'
LAUNCHER_NAME=DISPLAY_NAME+'.exe' if EDITION!='combined' else 'Desktop Companion.exe'
INSTALLATION_ID=hashlib.sha256(str(ROOT).casefold().encode()).hexdigest()[:16]
