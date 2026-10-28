"""Public PMX browsing names follow source folders, independently of ZIP roots."""
from pathlib import PurePosixPath


def pmx_library_name(source, multiple=False):
    path = PurePosixPath(source)
    if path.is_absolute() or any(part in ('.', '..') or '\\' in part for part in path.parts):
        raise ValueError('Unsafe PMX source path.')
    # A model file is the leaf card. Its containing directory is still a
    # directory even when it contains just one file with the same name.
    parts = [*path.parent.parts,path.stem]
    return ' / '.join(parts)


def pending_pmx_sources(files, prepared):
    known = {entry.get('variant_model') or str(entry.get('preview_model', '')).removeprefix('pmx/')
             for entry in prepared.values()}
    return {path for path in files if path.lower().endswith('.pmx') and path not in known}


def source_package_prefix(path):
    parts = PurePosixPath(path).parts
    return '/'.join(parts[:2] if len(parts) > 2 else parts[:1]) + '/'
