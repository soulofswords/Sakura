"""Launch a user-selected complete MikuMikuDance installation."""
import os
from pathlib import Path
import subprocess


def find_mmd(value):
    if not isinstance(value,str) or not value.strip():return None
    path=Path(value).expanduser()
    if path.is_dir():path=path/'MikuMikuDance.exe'
    if path.name.casefold()!='mikumikudance.exe' or not path.is_file():return None
    if not (path.parent/'Data').is_dir():return None
    return path.resolve()


def open_mmd(value):
    if os.name!='nt':raise RuntimeError('MikuMikuDance is available on Windows.')
    path=find_mmd(value)
    if path is None:raise ValueError('Choose MikuMikuDance.exe from its complete installation folder.')
    subprocess.Popen([str(path)],cwd=str(path.parent),creationflags=subprocess.CREATE_NO_WINDOW)
    return {'opened':True,'message':'MikuMikuDance opened. Use its model Load button to choose your PMX.'}
