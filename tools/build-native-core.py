"""Compile proprietary root Python modules into a Windows extension."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'tools/protected-build/native';OUT.mkdir(parents=True,exist_ok=True)
files=sorted(BASE.glob('*.py'))
fingerprint=hashlib.sha256(b''.join(path.name.encode()+path.read_bytes() for path in files)).hexdigest()
stamp=OUT/'Fingerprint.txt'
if stamp.exists() and stamp.read_text()==fingerprint and list(OUT.glob('sakura_core*.pyd')):
    print('Native core is current');sys.exit(0)
source=OUT/'source';source.mkdir(exist_ok=True)
for path in files:shutil.copy2(path,source/path.name)
(source/'sakura_core.py').write_text('"""Compiled Sakura application modules."""\n',encoding='utf-8')
command=[sys.executable,'-m','nuitka','--module','--nofollow-imports','--mingw64','--assume-yes-for-downloads',
    '--file-reference-choice=runtime','--python-flag=no_docstrings','--output-dir='+str(OUT),'--jobs=4',
    *['--include-module='+path.stem for path in files],str(source/'sakura_core.py')]
environment={**os.environ,'PYTHONPATH':str(source),'NUITKA_CACHE_DIR':str(BASE/'tools/nuitka-cache')}
try:
    subprocess.run(command,cwd=source,env=environment,check=True)
    assert list(OUT.glob('sakura_core*.pyd'))
    stamp.write_text(fingerprint)
    (OUT/'Build.md').write_text('# Native application core\n\nPASS: proprietary Python modules compiled into sakura_core.pyd.\nNo claim of irreversible encryption.\n',encoding='utf-8')
except Exception:
    import traceback
    (OUT/'Errors.md').write_text(traceback.format_exc(),encoding='utf-8');raise
