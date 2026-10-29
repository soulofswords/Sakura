"""Cross-process Windows/POSIX state locking with bounded retry and atomic replace."""
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def state_lock(path,timeout=5):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    handle=path.with_suffix(path.suffix+'.lock').open('a+b')
    handle.seek(0,2)
    if handle.tell()==0:handle.write(b'0');handle.flush()
    deadline=time.monotonic()+timeout;locked=False
    try:
        while True:
            try:
                handle.seek(0)
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
                locked=True;break
            except OSError:
                if time.monotonic()>=deadline:raise TimeoutError('Private state is busy. Try again shortly.') from None
                time.sleep(.025)
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_UN)
        handle.close()


def atomic_text(path,text):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    descriptor,temp=tempfile.mkstemp(prefix='.'+path.name+'-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8',newline='\n') as handle:
            handle.write(text);handle.flush();os.fsync(handle.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
