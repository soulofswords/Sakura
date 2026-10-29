"""Refuse credentials and links before exposing a host tree to a container."""
import fnmatch
import os
from pathlib import Path

BLOCKED=('.ssh','.aws','.gnupg','.kube','.npmrc','.pypirc','.netrc','.env','.env.*',
         '*.pem','*.key','*.p12','*.pfx','id_rsa','id_ed25519',
         '.git/config','.docker/config.json','.config/gcloud','credentials.json',
         'settings.json','.gemini-key.bin','.jio-owner-session.bin')


def validate_mount(workspace):
    root=Path(workspace)
    if root.is_symlink() or root.is_junction():raise ValueError('Container mounts cannot expose a symlink or junction workspace.')
    root=root.resolve(strict=True);count=0
    if any(part.casefold() in {'.ssh','.aws','.gnupg','.kube'} for part in root.parts):raise ValueError('Private credential directories cannot be mounted.')
    if root==Path.home().resolve() or root==Path(root.anchor):raise ValueError('Choose a dedicated task folder, not your home or a drive root, for containers.')
    for current,dirs,files in os.walk(root,followlinks=False,onerror=lambda error: (_ for _ in ()).throw(error)):
        for name in dirs+files:
            count+=1
            if count>50000:raise ValueError('Container mount scan exceeded 50,000 entries. Choose a smaller task folder.')
            entry=Path(current)/name;relative=entry.relative_to(root).as_posix().lower()
            if entry.is_symlink() or entry.is_junction():raise ValueError('Container workspace contains a symlink or junction. Use a clean task folder.')
            if any(fnmatch.fnmatchcase(relative,p) or fnmatch.fnmatchcase(name.lower(),p) or relative.endswith('/'+p) for p in BLOCKED):
                raise ValueError('Container workspace contains protected credentials/configuration ('+relative+'). Use a dedicated folder without private files.')
    return True
