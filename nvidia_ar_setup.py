"""Inspect an optional NVIDIA SDK without downloading or loading its DLLs."""
import os
from pathlib import Path
import sys

DOWNLOAD_URL='https://catalog.ngc.nvidia.com/orgs/nvidia/teams/maxine/collections/maxine_ar_sdk'
FEATURES=('nvarfaceexpressions','nvarlandmarkdetection','nvarfaceboxdetection')

def sdk_status(folder='', *, platform=sys.platform):
    root=Path(folder).expanduser() if folder else Path(os.environ.get('ARSDK_ROOT',str(Path(os.environ.get('ProgramFiles','C:/Program Files'))/'NVIDIA Corporation/NVIDIA AR SDK')))
    result={'platform_supported':platform=='win32','folder':str(root),'installed':False,'features':{},'download_url':DOWNLOAD_URL,'tracking_ready':False}
    if platform!='win32':result['message']='NVIDIA RTX expression tracking requires a supported Windows RTX PC.';return result
    if not root.is_dir():result['message']='Optional SDK is not installed. Nothing has been downloaded.';return result
    files=[]
    for directory,folders,names in os.walk(root,followlinks=False):
        folders[:]=[name for name in folders if not (Path(directory)/name).is_symlink()]
        files.extend(Path(directory)/name for name in names if not (Path(directory)/name).is_symlink())
        if len(files)>20000:result['message']='Choose the SDK directory itself, rather than a whole drive or software folder.';return result
    paths=[str(p.relative_to(root)).lower() for p in files]
    core=any(p.name.lower() in ('nvarpose.dll','nvar.dll') for p in files)
    features={name:any(name in path and path.endswith('.dll') for path in paths) for name in FEATURES}
    result.update(installed=core,features=features)
    result['message']='SDK files detected. Native expression inference still needs integration and verification against this SDK version.' if core else 'SDK Core DLL was not found in this folder.'
    return result
