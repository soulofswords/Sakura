"""Build and package the isolated, source-available Sakura DirectShow camera."""
from pathlib import Path
import shutil
import subprocess
import zipfile

BASE=Path(__file__).resolve().parents[1]
ROOT=BASE/'native'/'sakura-camera'
REVISION='72e86655715d9a25d69ce446aa4dd44ba58e10d2'

def run(*args, cwd=ROOT):
    subprocess.run(list(map(str,args)),cwd=cwd,check=True)

def main():
    source=ROOT/'obs-source'
    if not (source/'.git').exists():
        run('git','clone','--filter=blob:none','--sparse','https://github.com/obsproject/obs-studio.git',source)
    run('git','fetch','--depth','1','origin',REVISION,cwd=source)
    run('git','checkout','--detach',REVISION,cwd=source)
    run('git','sparse-checkout','set','plugins/win-dshow/virtualcam-module','shared/obs-shared-memory-queue','shared/obs-tiny-nv12-scale','libobs/util','deps/libdshowcapture',cwd=source)
    run('git','submodule','update','--init','--depth','1','deps/libdshowcapture/src',cwd=source)
    cmake=shutil.which('cmake')
    if not cmake:
        finder=Path('C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe')
        if finder.exists():
            install=subprocess.check_output([str(finder),'-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
            candidate=Path(install)/'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
            if candidate.is_file():cmake=str(candidate)
    if not cmake:raise RuntimeError('Install Visual Studio 2022 C++ Build Tools with CMake and Windows SDK first.')
    run(cmake,'-S',ROOT,'-B',ROOT/'build','-A','x64')
    run(cmake,'--build',ROOT/'build','--config','Release','--parallel','4')
    shutil.copy2(source/'COPYING',ROOT/'COPYING')
    with zipfile.ZipFile(ROOT/'source.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in source.rglob('*'):
            if path.is_file() and '.git' not in path.relative_to(source).parts:
                archive.write(path,'obs-source/'+path.relative_to(source).as_posix())
        for name in ('CMakeLists.txt','producer.cpp','placeholder.cpp','camera.def','README.md','COPYING','install-camera.ps1'):
            archive.write(ROOT/name,name)
        archive.write(__file__,'tools/build-sakura-camera.py')
    print('Built Sakura camera filter, frame bridge and corresponding source archive.')

if __name__=='__main__':main()
