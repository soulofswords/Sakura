"""Stage model packages before publishing them to the model library."""
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import uuid
import re
import zipfile
from model_rig_validation import pmx_bone_names, validate_humanoid_names, validate_vrm_glb

MAX_BYTES = 512 * 1024 * 1024


def safe_path(name):
    path = PurePosixPath(name.replace('\\', '/'))
    if path.is_absolute() or '..' in path.parts or any(':' in part for part in path.parts):
        raise ValueError('The model package contains an unsafe file path.')
    return Path(*path.parts)


def model_folder_name(root, kind, label, identifier=''):
    label=re.sub(r'[<>:"/\\|?*\x00-\x1f]', '-', str(label)).strip(' .-')[:90].rstrip(' .') or 'Model'
    if label.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:label='Model '+label
    if not (root/kind/label).exists():return label
    suffix=re.sub('[^A-Za-z0-9_-]','',str(identifier))[-12:] or uuid.uuid4().hex[:8]
    name=label+' '+suffix
    while (root/kind/name).exists():name=label+' '+uuid.uuid4().hex[:8]
    return name


def import_package(root, files, model_format="auto", display_name='', identifier=''):
    if model_format not in {"auto", "pmx", "vrm", "live2d"}:
        raise ValueError("Choose PMX, VRM, or Live2D.")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sakura-model-') as staging:
        stage = Path(staging)
        total = 0
        for name, content in files:
            if name.lower().endswith('.zip'):
                import io
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    for member in archive.infolist():
                        relative = safe_path(member.filename)
                        if member.is_dir():
                            continue
                        total += member.file_size
                        if total > MAX_BYTES or len(archive.infolist()) > 5000:
                            raise ValueError('Model packages must be under 512 MB and 5,000 files.')
                        target = stage / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(member) as source, target.open('wb') as output:
                            shutil.copyfileobj(source, output)
            else:
                relative = safe_path(name)
                total += len(content)
                if total > MAX_BYTES:
                    raise ValueError('Model packages must be under 512 MB.')
                target = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
        live2d = sorted(stage.rglob('*.model3.json'))
        if model_format == 'live2d' or (model_format == 'auto' and live2d and not any(p.suffix.lower() in {'.pmx', '.vrm'} for p in stage.rglob('*'))):
            if not live2d:
                raise ValueError('Choose the complete Live2D folder containing a .model3.json file, .moc3 file, and textures.')
            import json
            for descriptor in live2d:
                metadata = json.loads(descriptor.read_text(encoding='utf-8-sig'))
                references = metadata.get('FileReferences', {})
                required = [references.get('Moc', '')] + references.get('Textures', [])
                if not required[0] or not references.get('Textures'):
                    raise ValueError('Live2D model must reference its MOC3 file and textures.')
                for reference in required:
                    target = descriptor.parent / safe_path(reference)
                    if not target.is_file():
                        raise ValueError(f'Live2D asset is missing: {reference}')
                if (descriptor.parent / safe_path(required[0])).read_bytes()[:4] != b'MOC3':
                    raise ValueError('Live2D MOC3 file is invalid.')
            descriptor=live2d[0]
            inferred=descriptor.name[:-len('.model3.json')]
            if inferred.lower() in ('model','avatar','character') and descriptor.parent!=stage:inferred=descriptor.parent.name
            label=str(display_name).replace('\\','/').split('/')[-1].strip() or inferred
            name = model_folder_name(root,'live2d',label,identifier)
            destination = root / 'live2d' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(stage, destination)
            return {'models': [f'live2d/{name}/{p.relative_to(stage).as_posix()}' for p in live2d],
                    'renderable': True, 'message': 'Live2D package imported with textures, physics and expressions.'}
        models = sorted(p for p in stage.rglob('*') if p.suffix.lower() in {'.pmx', '.vrm'})
        if model_format != 'auto' and (not models or any(p.suffix.lower() != '.' + model_format for p in models)):
            raise ValueError(f'Use the {model_format.upper()} button with a matching model package.')
        if not models:
            raise ValueError('Choose a PMX folder, VRM file, or ZIP containing a model.')
        for model in models:
            with model.open('rb') as source:
                header = source.read(9)
            if model.suffix.lower() == '.vrm':
                validate_vrm_glb(model.read_bytes(), model.name)
            elif len(header) < 9 or header[:4] != b'PMX ':
                raise ValueError(f'{model.name} is not a valid PMX file.')
            else:
                validate_humanoid_names(pmx_bone_names(model.read_bytes()), model.name)
        published = []
        for kind in sorted({model.suffix.lower().lstrip('.') for model in models}):
            first=next(model for model in models if model.suffix.lower()=='.'+kind)
            inferred=first.stem
            if inferred.lower() in ('model','avatar','character') and first.parent!=stage:inferred=first.parent.name
            label=str(display_name).replace('\\','/').split('/')[-1].strip() or inferred
            name=model_folder_name(root,kind,label,identifier)
            destination = root / kind / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            def ignore_other_models(directory, names):
                return [entry for entry in names if Path(entry).suffix.lower() in {'.pmx', '.vrm'} and Path(entry).suffix.lower() != '.' + kind]
            shutil.copytree(stage, destination, ignore=ignore_other_models)
            published.extend(f'{kind}/{name}/{model.relative_to(stage).as_posix()}' for model in models if model.suffix.lower() == '.' + kind)
        return {'models': published,
                'message': 'Imported into its format folder with textures and folder structure preserved.'}
