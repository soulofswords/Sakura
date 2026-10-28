"""Wait for the owner account2 sync, then verify the combined hosted library."""
import ctypes,json,time,sys,importlib.util
from ctypes import wintypes
from pathlib import Path
root=Path(__file__).resolve().parents[1];directory=root.parent/'private-model-library-account2-pmx'
status=directory/'publication-completion.json'
def record(state,**extra):
    temp=status.with_suffix('.tmp');temp.write_text(json.dumps({'state':state,'updated_at':time.time(),**extra}),encoding='utf-8');temp.replace(status)
kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.OpenProcess.restype=wintypes.HANDLE;kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];kernel.CloseHandle.argtypes=[wintypes.HANDLE]
record('syncing')
try:
    handle=kernel.OpenProcess(0x00100000,False,int(sys.argv[1]))
    if handle:
        try:
            while kernel.WaitForSingleObject(handle,30000)==258:pass
        finally:kernel.CloseHandle(handle)
    if not (directory/'prepared-models.json').is_file():raise ValueError('Second-account packages were not prepared. Check the private sync log.')
    record('checking_authenticated_download')
    spec=importlib.util.spec_from_file_location('verify_jio',root/'tools/verify-jio-publication.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result=module.verify(root);record('complete',**result)
except Exception as error:record('failed',error=str(error)[:250] if isinstance(error,ValueError) else type(error).__name__)
