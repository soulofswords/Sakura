"""Inspect the real EXE/APK archives without installing or launching them."""
import hashlib,json,lzma,mmap,tempfile,zipfile
from pathlib import Path
import argparse

PERSONAL_EXTENSIONS={'.pmx','.pmd','.vrm','.moc3','.gguf','.safetensors','.pth','.pt','.index'}
PERSONAL_NAMES={'agent-learning.json','agent-learning.tmp','.gemini-key.bin','.cloud-keys.bin','.library-publisher.bin','.library-publisher.tmp','phone-devices.json','conversation-memory.json','agent-connections.json','agent-task-history.json','agent-automations.json','agent-automations.tmp','phone-link.key','google-token.json'}
def inspect(archive,windows):
    names=archive.namelist()
    assert len(names)==len(set(names)),'Duplicate archive entries'
    leaks=[n for n in names if Path(n).suffix.lower() in PERSONAL_EXTENSIONS or Path(n).name in PERSONAL_NAMES or '/agent-local-ai/' in n or n.startswith(('Sakura/models/','Sakura/voices/','Sakura/llm-models/','Sakura/rvc-assets/'))]
    assert not leaks,'Personal assets/credentials leaked: '+str(leaks)
    backups=[n for n in names if n.lower().endswith(('.bak','.backup','.orig','.rej','.tmp','.map','~')) or '.before-' in n.lower()]
    assert not backups,'Backup/debug sources leaked: '+str(backups)
    if windows:
        assert any(n.startswith('Sakura/sakura_core') and n.endswith('.pyd') for n in names)
        root_py=[n for n in names if n.startswith('Sakura/') and n.count('/')==1 and n.endswith(('.py','.pyc'))]
        assert sorted(root_py)==['Sakura/desktop.py','Sakura/sitecustomize.py']
        viewer=archive.read('Sakura/static/js/model-viewer.js').decode()
        # Only two things are provable from protected JavaScript: that protection ran,
        # and that a top-level name survived it. Implementation names are rewritten into
        # string form and some are hoisted into the encoded array, so they cannot be
        # searched for here; release-protection.py asserts them while still readable.
        assert '_0x' in viewer and 'SmartTgaLoader' in viewer,'Shipped renderer is unprotected or not this release\'s first-party module'
        assert 'Sakura/static/model-library-preview.html' in names,'Character library preview page is not packaged'
        assert 'Sakura/static/js/pmx-stage.js' in names,'PMX scenery controls are not packaged'
        for module in ('av','psutil','mcp','playwright'):
            assert 'Sakura/runtime/Lib/site-packages/'+module+'/__init__.py' in names,'Required packaged dependency missing: '+module
        assert 'Sakura/workers/rvc-worker.py' in names,'Protected RVC bootstrap missing'
        assert 'Sakura/setup-rvc-amd.ps1' in names,'Optional RVC setup is missing'
        assert 'eye-tracking.js?v=cursor-gpu6' in archive.read('Sakura/static/js/app.js').decode(),'Shipped app.js pins a stale eye-tracking cache'
    else:
        assert 'classes.dex' in names and 'assets/mobile.js' in names
        assert '_0x' in archive.read('assets/mobile.js').decode()
        mobile=archive.read('assets/static/js/model-viewer.js').decode()
        assert '_0x' in mobile and 'SmartTgaLoader' in mobile,'Shared mobile renderer is unprotected or stale'
    return {'files':len(names),'personal_models_or_credentials':leaks,'backup_or_debug_sources':backups,'protected_code':True,'protected_renderer':True}

def verify(path):
    if path.suffix=='.apk':
        with zipfile.ZipFile(path) as archive:result=inspect(archive,False)
    else:
        with path.open('rb') as source,mmap.mmap(source.fileno(),0,access=mmap.ACCESS_READ) as view,tempfile.TemporaryFile() as payload:
            offset=view.find(b'\xfd7zXZ\x00');assert offset>=0,'Missing EXE payload';source.seek(offset)
            decoder=lzma.LZMADecompressor()
            while not decoder.eof:
                payload.write(decoder.decompress(source.read(1024*1024) if decoder.needs_input else b'',max_length=8*1024*1024))
            payload.seek(0)
            with zipfile.ZipFile(payload) as archive:result=inspect(archive,True)
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    return {'file':path.name,'size':path.stat().st_size,'sha256':digest,**result}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('files',type=Path,nargs='+');parser.add_argument('--report',type=Path)
    args=parser.parse_args();results=[]
    for file in args.files:
        result=verify(file);results.append(result);print(json.dumps(result),flush=True)
    if args.report:args.report.write_text(json.dumps(results,indent=2),encoding='utf-8')
