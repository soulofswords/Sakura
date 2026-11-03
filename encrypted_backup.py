"""Password-encrypted local exports. No credentials, browsers or cloud sessions."""
import json
import os
from pathlib import Path,PurePosixPath
import secrets
import shutil
import sqlite3
import tempfile
import zipfile

MAGIC=b'SAKURA-BACKUP-1\n'
MAX_BYTES=30*1024**3
MAX_FILES=60000
STATE={'memory.json','trusted_memory.json','desktop-profile/companion-memory.sqlite3',
       'desktop-profile/agent-learning.json','desktop-profile/agent-knowledge.sqlite3',
       'desktop-profile/agent-task-history.sqlite3','desktop-profile/agent-skills.json',
       'desktop-profile/memory-workbench.sqlite3','desktop-profile/agent-audit.sqlite3',
       'desktop-profile/archaeology.sqlite3'}
ASSETS={'.pmx','.pmd','.vrm','.moc3','.json','.png','.jpg','.jpeg','.webp','.bmp','.tga','.dds','.sph','.spa','.txt','.vmd','.vpd','.wav','.mp3'}

def allowed(name):
    p=PurePosixPath(name)
    return not ('\\' in name or ':' in name or p.is_absolute() or '..' in p.parts) and (name in STATE or len(p.parts)>2 and p.parts[0]=='models' and p.suffix.lower() in ASSETS)

def derive(password,salt):
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    if not isinstance(password,str) or not 12<=len(password)<=1024:raise ValueError('Use a backup password of at least 12 characters. Keep it safe; Sakura cannot recover it.')
    return PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=salt,iterations=600000).derive(password.encode())

def create(root,destination,password):
    from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
    root=Path(root).resolve();destination=Path(destination)
    if destination.exists():raise ValueError('Choose a new backup filename; existing files are not overwritten.')
    salt=secrets.token_bytes(16);nonce=secrets.token_bytes(12);header=MAGIC+salt+nonce;key=derive(password,salt)
    paths=[]
    for relative in STATE:
        p=root/relative
        if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root):paths.append(p)
    models=root/'models'
    if models.is_dir() and not models.is_symlink():
        for directory,folders,files in os.walk(models,followlinks=False):
            folders[:]=[f for f in folders if not (Path(directory)/f).is_symlink()]
            for name in files:
                p=Path(directory)/name
                if not p.is_symlink() and p.resolve().is_relative_to(root) and allowed(p.relative_to(root).as_posix()):paths.append(p)
    total=sum(p.stat().st_size for p in paths)
    if total>MAX_BYTES or len(paths)>MAX_FILES:raise ValueError('This backup exceeds the 30 GiB / 60,000 file limit. Export smaller character libraries separately.')
    if shutil.disk_usage(destination.parent).free<total*2+50*1024**2:raise ValueError('Not enough free disk space to build and encrypt this backup.')
    with tempfile.TemporaryDirectory(prefix='.sakura-backup-',dir=destination.parent) as scratch:
        scratch=Path(scratch);archive=scratch/'payload.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as output:
            for p in paths:
                relative=p.relative_to(root).as_posix()
                if p.suffix=='.sqlite3':
                    snapshot=scratch/'snapshot.sqlite3'
                    with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True) as source,sqlite3.connect(snapshot) as target:source.backup(target)
                    output.write(snapshot,relative);snapshot.unlink()
                else:output.write(p,relative)
        encrypted=scratch/'encrypted';encryptor=Cipher(algorithms.AES(key),modes.GCM(nonce)).encryptor();encryptor.authenticate_additional_data(header)
        with archive.open('rb') as source,encrypted.open('wb') as out:
            out.write(header)
            for chunk in iter(lambda:source.read(1024**2),b''):out.write(encryptor.update(chunk))
            out.write(encryptor.finalize());out.write(encryptor.tag)
        os.link(encrypted,destination)  # exclusive final publication, never overwrite
    return {'ok':True,'path':str(destination),'files':len(paths),'source_bytes':total}

def restore(backup,parent,password):
    from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
    from cryptography.exceptions import InvalidTag
    backup=Path(backup);parent=Path(parent).resolve()
    size=backup.stat().st_size;header_size=len(MAGIC)+28
    if size<header_size+16 or size>MAX_BYTES+1024**3:raise ValueError('Unsupported or oversized backup.')
    with backup.open('rb') as f:
        header=f.read(header_size)
        if not header.startswith(MAGIC):raise ValueError('This is not a Sakura encrypted backup.')
        key=derive(password,header[len(MAGIC):len(MAGIC)+16]);nonce=header[-12:];f.seek(-16,2);tag=f.read(16);f.seek(header_size)
        with tempfile.TemporaryDirectory(prefix='.sakura-restore-',dir=parent) as scratch:
            scratch=Path(scratch);archive=scratch/'payload.zip';decryptor=Cipher(algorithms.AES(key),modes.GCM(nonce,tag)).decryptor();decryptor.authenticate_additional_data(header)
            try:
                with archive.open('wb') as out:
                    remaining=size-header_size-16
                    while remaining:
                        chunk=f.read(min(1024**2,remaining))
                        if not chunk:raise ValueError('The backup is incomplete.')
                        out.write(decryptor.update(chunk));remaining-=len(chunk)
                    out.write(decryptor.finalize())
            except InvalidTag:raise ValueError('The password is incorrect or the backup was modified. Nothing was restored.') from None
            extracted=scratch/'restored';extracted.mkdir()
            with zipfile.ZipFile(archive) as bundle:
                files=bundle.infolist();names=set();total=0
                if len(files)>MAX_FILES:raise ValueError('Too many backup files.')
                for item in files:
                    name=item.filename;folded=name.casefold();total+=item.file_size
                    if not allowed(name) or folded in names or total>MAX_BYTES or (item.external_attr>>16)&0o170000==0o120000:raise ValueError('The backup contains an unsafe or unsupported entry.')
                    names.add(folded)
                if shutil.disk_usage(parent).free<total+50*1024**2:raise ValueError('Not enough disk space to restore.')
                for item in files:
                    target=extracted.joinpath(*PurePosixPath(item.filename).parts);target.parent.mkdir(parents=True,exist_ok=True)
                    with bundle.open(item) as src,target.open('xb') as dst:shutil.copyfileobj(src,dst)
            destination=parent/('Sakura-Restore-'+secrets.token_hex(6));extracted.rename(destination)
    return {'ok':True,'path':str(destination),'files':len(files),'message':'Restored to a new folder. Your active installation was not overwritten. Import recovered characters from its models folder; close Sakura before replacing memory databases.'}
