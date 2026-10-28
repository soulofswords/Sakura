"""Current-user Windows sign-in startup for Companion; no admin rights needed."""
import os
from pathlib import Path
import subprocess
import sys

VALUE='Sakura Companion'
RUN_KEY=r'Software\Microsoft\Windows\CurrentVersion\Run'

def command(base=None):
    base=Path(base or Path(__file__).parent).resolve()
    candidates=[base.parent/'Sakura Companion.exe',base.parent.parent/'Sakura Companion.exe']
    launcher=next((path for path in candidates if path.is_file()),None)
    if launcher:return subprocess.list2cmdline([str(launcher),'--windows-startup'])
    python=base/'runtime/pythonw.exe'
    if not python.is_file():python=base/'venv/Scripts/pythonw.exe'
    if not python.is_file():python=Path(sys.executable)
    return subprocess.list2cmdline([str(python),str(base/'windows_startup.py'),'--launch'])


def status():
    if os.name!='nt':return {'supported':False,'enabled':False}
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,RUN_KEY) as key:value=winreg.QueryValueEx(key,VALUE)[0]
    except FileNotFoundError:value=''
    disabled=False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run') as key:
            state=winreg.QueryValueEx(key,VALUE)[0]
            disabled=isinstance(state,bytes) and len(state)>=4 and int.from_bytes(state[:4],'little') in (3,7)
    except FileNotFoundError:pass
    return {'supported':True,'enabled':bool(value) and not disabled,'registered':bool(value),'disabled_by_windows':disabled,'command':value}


def configure(enabled):
    if type(enabled) is not bool:raise ValueError('Startup must be enabled or disabled.')
    if os.name!='nt':raise ValueError('Windows startup is only available on Windows.')
    from product import EDITION
    if EDITION=='vtuber':raise ValueError('Automatic startup is a Companion setting.')
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,RUN_KEY) as key:
        if enabled:winreg.SetValueEx(key,VALUE,0,winreg.REG_SZ,command())
        else:
            try:winreg.DeleteValue(key,VALUE)
            except FileNotFoundError:pass
    if enabled:
        # An explicit tick restores Sakura only if Task Manager previously disabled it.
        approved=r'Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run'
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,approved) as key:
            try:winreg.DeleteValue(key,VALUE)
            except FileNotFoundError:pass
    return status()

if __name__=='__main__' and sys.argv[1:]==['--launch']:
    # Development installs without a launcher still use saved settings and a fixed cwd.
    import runpy
    base=Path(__file__).resolve().parent;os.chdir(base)
    os.environ['SAKURA_DESKTOP']='1';os.environ['SAKURA_UPLOAD_UI']='1';os.environ['SAKURA_START_MODE']='resume'
    runpy.run_path(str(base/'desktop.py'),run_name='__main__')
