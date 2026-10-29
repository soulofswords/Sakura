"""Restrict legacy installation-local personal state to the owning Windows user.

Models and voices are never moved, removed or recursively inspected here.
The default installer is per-user. This also repairs custom/shared-drive installs.
"""
import os
from pathlib import Path


def protect_installation_state(root):
    if os.name!='nt':return
    from mobile_tls import restrict_private_key
    root=Path(root).resolve()
    # Restrict inheritance for future settings/secret atomic replacements.
    restrict_private_key(root)
    for path in root.iterdir():
        if path.is_file() and not path.is_symlink() and (path.suffix in ('.json','.bin','.key','.jsonl','.sqlite','.db') or path.name.endswith(('.sqlite-wal','.sqlite-shm','.db-wal','.db-shm'))):
            restrict_private_key(path)
    for name in ('logs','audio','desktop-profile'):
        folder=root/name
        if folder.is_symlink() or not folder.is_dir():continue
        restrict_private_key(folder)
        for directory,folders,files in os.walk(folder,followlinks=False):
            folders[:]=[name for name in folders if not (Path(directory)/name).is_symlink()]
            for name in folders+files:
                path=Path(directory)/name
                if not path.is_symlink():restrict_private_key(path)
