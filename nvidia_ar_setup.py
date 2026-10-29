"""Inspect an optional NVIDIA SDK without downloading or loading its DLLs."""
import os
from pathlib import Path
import sys

DOWNLOAD_URL='https://catalog.ngc.nvidia.com/orgs/nvidia/maxine/collections/maxine_ar_sdk/-'
CORE_DOWNLOAD_URL='https://catalog.ngc.nvidia.com/orgs/nvidia/maxine/resources/ar_sdk_core/1.2.0.0_windows/download-file?path=ARSDK_windows_1.2.0.0.zip'
FEATURES=('nvarfaceexpressions','nvarlandmarkdetection','nvarfaceboxdetection')

def _sdk_root_candidates(folder=''):
    candidates=[]
    if folder:
        candidates.append(Path(folder).expanduser())
    else:
        env_root=os.environ.get('ARSDK_ROOT')
        if env_root:candidates.append(Path(env_root).expanduser())
        candidates.append(Path(os.environ.get('ProgramFiles','C:/Program Files'))/'NVIDIA Corporation/NVIDIA AR SDK')
        # Custom SDKs must come from the user's saved selection or ARSDK_ROOT,
        # never from a developer-specific writable drive path.
    seen=set()
    for candidate in candidates:
        try:candidate=candidate.resolve()
        except OSError:continue
        if candidate in seen:continue
        seen.add(candidate)
        nested=[candidate,candidate/'ARSDK']
        try:nested.extend(candidate.glob('sdk-*/ARSDK'))
        except OSError:pass
        for root in nested:
            if (root/'bin'/'nvARPose.dll').is_file():
                yield root

def sdk_status(folder='', *, platform=sys.platform):
    requested=Path(folder).expanduser() if folder else None
    root=next(_sdk_root_candidates(folder),requested or Path(os.environ.get('ARSDK_ROOT',str(Path(os.environ.get('ProgramFiles','C:/Program Files'))/'NVIDIA Corporation/NVIDIA AR SDK'))))
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
    models=root/'bin'/'models'
    required_models=('face_expressions_fp16_mlp_86.engine.trtpkg','face_and_landmark_detector_119_fp32_86.engine.trtpkg','face_detection_86.engine.trtpkg')
    missing_models=[name for name in required_models if not (models/name).is_file()]
    ready=core and all(features.values()) and not missing_models
    result.update(installed=core,features=features,models_ready=not missing_models,tracking_ready=ready)
    missing_features=[name for name,present in features.items() if not present]
    if ready:
        result['message']='NVIDIA AR SDK face-expression tracker is ready for direct Sakura tracking.'
    elif not core:
        result['message']='SDK Core DLL was not found in this folder.'
    else:
        details=[]
        if missing_features:details.append('missing feature packages: '+', '.join(missing_features))
        if missing_models:details.append('missing model files: '+', '.join(missing_models))
        result['message']='SDK Core detected, but '+('; '.join(details) or 'the tracker prerequisites are incomplete')+'.'
    return result

def import_sdk_archive(archive, destination):
    """Extract a user-selected SDK archive without executing its contents."""
    import zipfile
    import shutil
    import uuid
    from pathlib import PurePosixPath
    root=Path(destination).resolve()/('sdk-'+uuid.uuid4().hex[:12])
    with zipfile.ZipFile(archive) as package:
        entries=package.infolist()
        if len(entries)>20000 or sum(entry.file_size for entry in entries)>8*1024**3:
            raise ValueError('SDK archive is too large or contains too many files.')
        for entry in entries:
            path=PurePosixPath(entry.filename.replace('\\','/'))
            if path.is_absolute() or '..' in path.parts or any(':' in part for part in path.parts) or (entry.external_attr>>16)&0o170000==0o120000:
                raise ValueError('SDK archive contains an unsafe path.')
        if not any(PurePosixPath(entry.filename.replace('\\','/')).name.lower() in ('nvarpose.dll','nvar.dll') for entry in entries):
            raise ValueError('This ZIP does not contain NVIDIA AR SDK Core. Choose ARSDK_windows_1.2.0.0.zip.')
        root.mkdir(parents=True,exist_ok=False)
        try:
            for entry in entries:
                target=root.joinpath(*PurePosixPath(entry.filename.replace('\\','/')).parts)
                if entry.is_dir():
                    target.mkdir(parents=True,exist_ok=True)
                else:
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with package.open(entry) as source,target.open('wb') as output:
                        shutil.copyfileobj(source,output)
            return sdk_status(str(root),platform='win32')
        except Exception:
            # Only remove the fresh directory created by this import.
            shutil.rmtree(root)
            raise
