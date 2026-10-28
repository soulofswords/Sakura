"""Owner-only scheduled publisher. Not a tester/client background process."""
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-credentials',required=True);parser.add_argument('--publish-url',required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    # A periodic trigger never starts a second upload over an active run.
    lock=(args.output/'publisher.lock').open('a+b')
    if sys.platform=='win32':
        import msvcrt
        lock.seek(0);lock.write(b'1');lock.flush();lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:return 0
    log=args.output/'publisher-sync.log'
    if log.exists() and log.stat().st_size>5_000_000:log.replace(log.with_suffix('.previous.log'))
    tools=Path(__file__).resolve().parent
    commands=[
        [str(tools/'publish-model-library.py'),'--workspace-credentials',args.source_credentials,'--output',str(args.output)],
        [str(tools/'upload-library-drive.py'),'--app',args.app,'--output',str(args.output)],
        [str(tools/'publish-library-catalogue.py'),'--app',args.app,'--output',str(args.output),'--url',args.publish_url,'--once'],
    ]
    with log.open('a',encoding='utf-8') as output:
        upload_status=0
        for index,command in enumerate(commands):
            interpreter=str(Path(sys.executable).with_name('python.exe')) if Path(sys.executable).name.lower()=='pythonw.exe' else sys.executable
            result=subprocess.run([interpreter,*command],stdout=output,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
            if index==1:upload_status=result.returncode;continue
            if result.returncode and not(index==0 and result.returncode==1):return result.returncode
    return upload_status


if __name__=='__main__':raise SystemExit(main())
