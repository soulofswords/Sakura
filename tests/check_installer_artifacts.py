"""Read-back release checks, independent of the packaging implementation."""
import hashlib
import io
import json
from pathlib import Path
import plistlib
import struct
import subprocess
import zipfile
import zlib
import argparse

BASE=Path(__file__).resolve().parents[1]
BUILD=BASE/'tools/installer-build'
OUT=Path('C:/AI')

def check_windows():
    with zipfile.ZipFile(BUILD/'windows-payload.zip') as archive:
        names=archive.namelist()
        assert len(names)==len(set(names)), 'Duplicate package entries'
        assert not any(name.startswith(('Sakura/models/','Sakura/voices/','Sakura/llm-models/','Sakura/ollama-runtime/','Sakura/rvc-assets/')) for name in names)
        assert not any(Path(name).name in ('.gemini-key.bin','conversation-memory.json','steam-shortcuts.json') for name in names)
        assert not any(Path(name).suffix.lower() in ('.pmx','.vrm','.gguf','.pth','.pt','.safetensors') for name in names)
        import importlib.util
        protected=any(name.startswith('Sakura/sakura_core') and name.endswith('.pyd') for name in names)
        if protected:
            assert 'Sakura/app.py' not in names and 'Sakura/llm.py' not in names
            assert not any(name.startswith('Sakura/__pycache__/app.') for name in names)
        for source_name in ([] if protected else [name for name in names if name.startswith('Sakura/') and name.count('/') == 1 and name.endswith('.py')]):
            cache_name = 'Sakura/__pycache__/' + Path(importlib.util.cache_from_source(Path(source_name).name)).name
            raw = archive.read(cache_name)
            assert raw[:4] == importlib.util.MAGIC_NUMBER, 'Bytecode runtime mismatch'
            assert int.from_bytes(raw[4:8], 'little') == 3, 'Expected checked-hash bytecode'
            assert raw[8:16] == importlib.util.source_hash(archive.read(source_name)), 'Stale application bytecode'
        cfg=json.loads(archive.read('Sakura/settings.json'))
        assert cfg['llm_provider']=='gemini' and not cfg['selected_model']
        assert not cfg['computer_control_enabled']
        assert cfg['selected_voice']=='sakura_ava'
        assert archive.testzip() is None
    target=BUILD/'smoke-install'
    exe=OUT/'Sakura-Setup-Windows-x64.exe'
    subprocess.run([str(exe),'--test-install',str(target)],check=True)
    # Verify files extracted from the EXE itself, rather than only the ZIP used to build it.
    with zipfile.ZipFile(BUILD/'windows-payload.zip') as archive:
        for name in archive.namelist():
            if name.endswith('/') or name=='Sakura/settings.json':continue
            installed=target/name
            assert installed.is_file(), 'Missing installed file: '+name
            assert hashlib.sha256(installed.read_bytes()).digest()==hashlib.sha256(archive.read(name)).digest(), 'Installed payload mismatch: '+name
    script='import app, webview, sounddevice, soundfile, pygame, faster_whisper, onnxruntime; from PySide6 import QtWebEngineWidgets; import local_model_setup; assert not local_model_setup.installed(); assert app.get_settings()["llm_provider"]=="gemini"; print("Portable dependencies and Gemini-only defaults: PASS")'
    subprocess.run([str(target/'Sakura/runtime/python.exe'),'-c',script],check=True,cwd=target/'Sakura')
    subprocess.run([str(target/'Desktop Companion.exe'),'--check'],check=True,cwd=target)
    settings=target/'Sakura/settings.json'; cfg=json.loads(settings.read_text())
    cfg.update(assistant_name='Upgrade preservation fixture',models_folder='custom-models',physics_boost=.85,
               physics_wind=.4,pmx_texture_reference=True,custom_future_option='keep')
    settings.write_text(json.dumps(cfg))
    fixture=target/'Sakura/models/pmx/keep-on-upgrade.txt';fixture.write_text('user asset')
    artwork=target/'Sakura/static/assets/desktop-companion.png'
    original_art=artwork.read_bytes();artwork.write_bytes(original_art+b'custom artwork fixture')
    own_art=artwork.parent/'user-art.txt';own_art.write_text('user artwork')
    subprocess.run([str(exe),'--test-install',str(target)],check=True)
    saved=json.loads(settings.read_text())
    for key in ('assistant_name','models_folder','physics_boost','physics_wind','pmx_texture_reference','custom_future_option'):
        assert saved[key]==cfg[key], 'Upgrade lost preference: '+key
    assert saved['preserve_configuration_on_reinstall'] is True
    assert list(settings.parent.glob('settings.json.before-update-*.json'))
    assert fixture.read_text()=='user asset'
    assert artwork.read_bytes()==original_art+b'custom artwork fixture' and own_art.read_text()=='user artwork'
    saved['preserve_configuration_on_reinstall']=False;settings.write_text(json.dumps(saved))
    subprocess.run([str(exe),'--test-install',str(target)],check=True)
    reset=json.loads(settings.read_text())
    assert reset['assistant_name']=='Sakura' and reset['physics_boost']==0 and reset['pmx_texture_reference'] is False
    assert reset['preserve_configuration_on_reinstall'] is False
    assert fixture.read_text()=='user asset' and own_art.read_text()=='user artwork'
    assert artwork.read_bytes()==original_art+b'custom artwork fixture'
    binary=target/'Desktop Companion.exe';before=hashlib.sha256(binary.read_bytes()).digest()
    settings.write_text('null')
    rejected=subprocess.run([str(exe),'--test-install',str(target)],capture_output=True)
    assert rejected.returncode!=0 and settings.read_text()=='null', 'Malformed settings were overwritten'
    assert hashlib.sha256(binary.read_bytes()).digest()==before, 'Binaries changed before invalid config was rejected'
    settings.write_text(json.dumps(reset))
    print('Windows extraction, imports, launcher, settings preservation/reset, user artwork and models: PASS')

def check_mac():
    import pycdlib
    data=(OUT/'Sakura-Setup-macOS-Apple-Silicon.dmg').read_bytes()
    footer=data[-512:];assert footer[:4]==b'koly'
    assert struct.unpack_from('>II',footer,4)==(4,512)
    offset,length=struct.unpack_from('>QQ',footer,216)
    metadata=plistlib.loads(data[offset:offset+length])
    table=metadata['resource-fork']['blkx'][0]['Data'];assert table[:4]==b'mish'
    assert struct.unpack_from('>I',table,200)[0]==2
    kind,_,first,count,position,size=struct.unpack_from('>IIQQQQ',table,204)
    assert kind==1 and first==0 and count*512==size
    raw=data[position:position+size];assert zlib.crc32(raw)&0xffffffff==struct.unpack_from('>I',footer,88)[0]
    image=pycdlib.PyCdlib();image.open_fp(io.BytesIO(raw))
    info=io.BytesIO();image.get_file_from_iso_fp(info,rr_path='/Sakura Installer.app/Contents/Info.plist')
    app=plistlib.loads(info.getvalue());assert app['CFBundleExecutable']=='Install'
    install=io.BytesIO();image.get_file_from_iso_fp(install,rr_path='/Sakura Installer.app/Contents/Resources/install.command')
    assert b'--prefer-binary' in install.getvalue() and b'83dcb047' in install.getvalue()
    source=io.BytesIO();image.get_file_from_iso_fp(source,rr_path='/Sakura Installer.app/Contents/Resources/source.zip')
    with zipfile.ZipFile(source) as archive:
        assert archive.testzip() is None
        assert not any(name.startswith(('Sakura/models/','Sakura/voices/','Sakura/llm-models/')) for name in archive.namelist())
        assert b"staging / 'bin'" in archive.read('Sakura/local_model_setup.py')
    record=image.get_record(rr_path='/Sakura Installer.app/Contents/MacOS/Install')
    assert record.rock_ridge.get_file_mode()&0o111
    image.close()
    print('macOS UDIF checksums, readable ISO volume, executable app bundle, source payload: PASS (native Mac execution NOT tested)')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--windows-only',action='store_true')
    parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--build-directory',type=Path,default=BUILD)
    args=parser.parse_args();OUT=args.output.resolve();BUILD=args.build_directory.resolve()
    check_windows()
    if not args.windows_only:check_mac()
