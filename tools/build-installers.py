"""Build sanitized Windows installer and unsigned Apple Silicon bootstrap DMG.

Only allowlisted application files are included, never user models, keys or memory.
"""
import hashlib
import io
import lzma
import json
from pathlib import Path
import plistlib
import shutil
import struct
import subprocess
import uuid
import zipfile
import zlib
import argparse
import sys

BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:sys.path.insert(0,str(BASE))
OUT = Path('C:/AI/Installer ready')
BUILD = BASE / 'tools/installer-build'
CSC = Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
CS_DIR=BASE/'launcher'
LAUNCHER_FILE='Desktop Companion.exe'
INSTALLER_FILE='Sakura-Setup-Windows-x64.exe'
MAC_NAME='Sakura Installer'
DMG_FILE='Sakura-Setup-macOS-Apple-Silicon.dmg'
MAC_README=None
PROTECT_RELEASE=True

def release_asset_allowed(name):
    """Never publish local source backups or debugging maps as application assets."""
    path=Path(name)
    lowered=path.name.lower()
    return not (any(part in ('__pycache__','.git','.pytest_cache') for part in path.parts)
        or lowered.endswith(('.bak','.backup','.orig','.rej','.tmp','.swp','.swo','.map','~'))
        or '.before-' in lowered)
DEFAULTS = {'llm_provider': 'gemini', 'selected_model': '', 'selected_voice': 'kokoro_af_heart',
            'ollama_model': 'qwen3-vl:2b-instruct', 'ollama_context': 2048,
            'ollama_models_folder': 'llm-models', 'computer_control_enabled': False,
            'screen_enabled': False, 'screen_reactions_enabled': False,
            'vtuber_tracking_only': False, 'rvc_model': '', 'rvc_index': '',
            'assistant_name': 'Sakura', 'user_address':'sir', 'wake_word': 'hey sakura', 'preserve_configuration_on_reinstall': True,
            'model_quality': 'balanced', 'physics_mode': 'custom', 'physics_boost': 0,
            'physics_enabled': True, 'physics_wind': 0, 'pmx_texture_reference': False}
def compile_cs(output, files, references=(), resource=None, bootstrap=None):
    args = [str(CSC), '/nologo', '/target:winexe', '/platform:x64', '/optimize+',
            '/reference:System.Windows.Forms.dll', '/reference:System.Drawing.dll',
            f'/win32icon:{globals().get("APP_ICON", BASE / "launcher/companion.ico")}', f'/out:{output}']
    args += [f'/reference:{ref}.dll' for ref in references]
    if resource: args += [f'/resource:{resource},SakuraPayload']
    if bootstrap: args += [f'/resource:{bootstrap},SakuraBootstrap']
    subprocess.run(args + [str(CS_DIR / file) for file in files], check=True)

def app_files():
    from kokoro_speech import ASSETS, _hash
    for name, (size,digest) in ASSETS.items():
        path=BASE/'kokoro-assets'/name
        if not path.is_file() or path.stat().st_size!=size or _hash(path)!=digest:
            raise RuntimeError('Kokoro speech assets are missing or invalid. Run tools/install-kokoro.py before building.')
        yield path,'Sakura/kokoro-assets/'+name
    for name in ('KOKORO-LICENSE.txt','KOKORO-ONNX-LICENSE.txt','ATTRIBUTION.txt'):
        yield BASE/'docs'/(Path(name).stem+'.md'),'Sakura/kokoro-assets/'+name
    for file in BASE.glob('*.py'):
        yield file, 'Sakura/' + file.name
    for name in ('requirements.txt','requirements-macos.txt','run-macos.command',
                 'setup-macos.command','setup-rvc-macos.command','requirements-rvc.txt',
                 'requirements-agent.txt'):
        yield BASE / name, 'Sakura/' + name
    yield BASE/'personality/sakura.txt', 'Sakura/personality/sakura.txt'
    for name in ('companion.ico','companion-vtuber.ico','vtuber.ico','model-upload.ico'):
        yield BASE/'launcher'/name,'Sakura/launcher/'+name
    yield BASE/'static/index.html','Sakura/static/index.html'
    yield BASE/'static/model-library-preview.html','Sakura/static/model-library-preview.html'
    camera=BASE/'native'/'sakura-camera'
    for name in ('bin/x64/sakura-camera64.dll','bin/x64/sakura-camera-bridge64.dll','install-camera.ps1','README.md','COPYING','source.zip'):
        path=camera/name
        if not path.is_file():raise RuntimeError('Build Sakura Virtual Camera before packaging: tools/build-sakura-camera.py')
        yield path,'Sakura/native/sakura-camera/'+name
    for folder in ('js','css','assets','vendor','audio'):
        for file in (BASE/'static'/folder).rglob('*'):
            if file.is_file() and release_asset_allowed(file):
                yield file, 'Sakura/' + file.relative_to(BASE).as_posix()

def windows():
    print('Building Windows payload…', flush=True)
    from build_bytecode import compile_application
    bytecode_files = [] if PROTECT_RELEASE else compile_application(BUILD/'application-bytecode')
    records=list(app_files())
    if PROTECT_RELEASE:
        import importlib.util
        spec=importlib.util.spec_from_file_location('release_protection',BASE/'tools/release-protection.py')
        protection=importlib.util.module_from_spec(spec);spec.loader.exec_module(protection)
        records=list(protection.protected_files(records,BUILD/'protection'))
    compile_cs(BUILD/LAUNCHER_FILE, ['Launcher.cs','StartupDialog.cs','LocalModelDialog.cs'], ['System.Web.Extensions'])
    compile_cs(BUILD/'Uninstall.exe',['Uninstall.cs'])
    payload=BUILD/'windows-payload.zip'; manifest=[]
    # Solid compression sees repeated code/data across packages; ZIP remains
    # the extraction manifest container, with every original file retained.
    with zipfile.ZipFile(payload,'w',compression=zipfile.ZIP_STORED) as output:
        def add(path,name):
            output.write(path,name);manifest.append(hashlib.sha256(path.read_bytes()).hexdigest()+'\t'+name)
        for path,name in records: add(path,name)
        # The Windows native comparison editor includes its companion DLLs,
        # plugins and original documentation. Never include character files.
        editor_root=BASE/'tools/pmx-editor'
        if not (editor_root/'PmxEditor.exe').is_file():
            raise FileNotFoundError('Restore tools/pmx-editor/PmxEditor.exe before packaging Windows.')
        for path in editor_root.rglob('*'):
            if path.is_file() and path.suffix.lower() not in ('.pmx','.pmd','.vrm','.vmd','.vpd','.log'):
                add(path,'Sakura/tools/pmx-editor/'+path.relative_to(editor_root).as_posix())
        for path,name in bytecode_files: add(path,name)
        add(BUILD/LAUNCHER_FILE,LAUNCHER_FILE)
        add(BUILD/'Uninstall.exe','Sakura/Uninstall.exe')
        with zipfile.ZipFile(BASE/'tools/packaging-cache/python-3.12.10-embed-amd64.zip') as python:
            for name in python.namelist():
                if name=='python312._pth':continue
                data=python.read(name);destination='Sakura/runtime/'+name
                output.writestr(destination,data);manifest.append(hashlib.sha256(data).hexdigest()+'\t'+destination)
        pth=b'python312.zip\n.\nLib/site-packages\n..\nimport site\n'
        output.writestr('Sakura/runtime/python312._pth',pth)
        manifest.append(hashlib.sha256(pth).hexdigest()+'\tSakura/runtime/python312._pth')
        packages=BASE/'venv/Lib/site-packages'
        for path in packages.rglob('*'):
            if not path.is_file():continue
            relative=path.relative_to(packages)
            if any(part in ('__pycache__','.pytest_cache','tests','test','datasets') for part in relative.parts):continue
            if relative.parts[0].startswith(('pytest','_pytest','pycdlib','onnxruntime-dml')):continue
            if relative.parts[0].startswith(('edge_tts','phonemizer_fork-')):continue
            if path.suffix.lower() in ('.pyc','.pmx','.vrm','.gguf','.safetensors','.pth'):continue
            add(path,'Sakura/runtime/Lib/site-packages/'+relative.as_posix())
        output.writestr('Sakura/settings.json',json.dumps(DEFAULTS,indent=2))
        output.writestr('Sakura/installed-files.tsv','\n'.join(manifest))
        output.writestr('Sakura/INSTALLATION.txt','Imported characters and RVC voices are empty. Kokoro speech voices are included. Qwen is optional and downloaded on request.\nPython and third-party library licenses are in runtime/ and each package dist-info/licenses directory.\n')
    print('Compiling Windows installer…',flush=True)
    compressed=BUILD/'windows-payload.xz'
    with payload.open('rb') as source,lzma.open(compressed,'wb',preset=6,check=lzma.CHECK_CRC64) as target:
        shutil.copyfileobj(source,target,1024*1024)
    bootstrap=BASE/'tools/packaging-cache/python-3.12.10-embed-amd64.zip'
    print(f'Solid payload: {payload.stat().st_size:,} → {compressed.stat().st_size:,} bytes; offline decoder included',flush=True)
    compile_cs(OUT/INSTALLER_FILE,['Installer.cs'],['System.IO.Compression','System.IO.Compression.FileSystem','System.Web.Extensions'],compressed,bootstrap)

MAC_INSTALL = r'''#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo "Sakura requires a native Apple Silicon Mac (M1 or newer)."; exit 1
fi
major="$(sw_vers -productVersion | cut -d. -f1)"
if ((major < 14)); then echo "macOS 14 or newer is required."; exit 1; fi
choice=$(/usr/bin/osascript -e 'choose from list {"Gemini API key (skip local AI)", "Local LLM (choose Qwen after setup)"} with title "Install Sakura Companion" with prompt "Kokoro speech is included. No character or RVC models are bundled. Install optional local AI?" default items {"Gemini API key (skip local AI)"}')
if [[ "$choice" == false ]]; then exit 0; fi
project="$HOME/Library/Application Support/Sakura Companion/Sakura"
mkdir -p "$project"
echo "Installing base app into $project"
/usr/bin/unzip -oq source.zip -d "$(dirname "$project")"
if [[ ! -f "$project/settings.json" ]]; then cp defaults.json "$project/settings.json"; fi
mkdir -p "$project/models/pmx" "$project/models/vrm" "$project/models/live2d" "$project/voices" "$project/audio" "$project/llm-models/blobs" "$project/llm-models/manifests"
if [[ ! -x "$project/mac-python/bin/python3.12" ]]; then
  cache="$(mktemp -d)"
  trap 'rm -rf "$cache"' EXIT
  echo "Downloading native Apple Silicon Python…"
  /usr/bin/curl --fail --location --retry 3 'https://github.com/astral-sh/python-build-standalone/releases/download/20261009/cpython-3.12.15%2B20261009-aarch64-apple-darwin-install_only.tar.gz' -o "$cache/python.tar.gz"
  echo '83dcb04777c798bd95f3687acf9ae84b09860272ee6bdfb05be8bcf9447f75b8  '"$cache/python.tar.gz" | /usr/bin/shasum -a 256 -c -
  /usr/bin/tar -xzf "$cache/python.tar.gz" -C "$cache"
  mv "$cache/python" "$project/mac-python"
fi
cd "$project"
if [[ ! -x .venv-macos/bin/python ]]; then mac-python/bin/python3.12 -m venv .venv-macos; fi
.venv-macos/bin/python -m pip install --upgrade pip
.venv-macos/bin/python -m pip install --prefer-binary -r requirements-macos.txt
.venv-macos/bin/python -c 'import app, webview, keyring, Quartz; from PySide6 import QtWebEngineWidgets; print("Sakura imports OK")'
wrapper="$HOME/Applications/Sakura Companion.app"
mkdir -p "$wrapper/Contents/MacOS" "$wrapper/Contents/Resources"
cp launcher/companion.icns "$wrapper/Contents/Resources/companion.icns"
cat > "$wrapper/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>CFBundleExecutable</key><string>Sakura</string><key>CFBundleName</key><string>Sakura Companion</string><key>NSHumanReadableCopyright</key><string>SoulOfSwords</string><key>CFBundleIdentifier</key><string>app.sakura.companion</string><key>CFBundleIconFile</key><string>companion.icns</string><key>CFBundlePackageType</key><string>APPL</string><key>LSMinimumSystemVersion</key><string>14.0</string><key>NSMicrophoneUsageDescription</key><string>Sakura uses your microphone when enabled.</string><key>NSCameraUsageDescription</key><string>Optional VTuber face and hand tracking.</string></dict></plist>
PLIST
cat > "$wrapper/Contents/MacOS/Sakura" <<'LAUNCH'
#!/bin/bash
set -euo pipefail
cd "$HOME/Library/Application Support/Sakura Companion/Sakura"
exec .venv-macos/bin/python startup_macos.py
LAUNCH
chmod +x "$wrapper/Contents/MacOS/Sakura"
echo "Installed. Open $wrapper to launch Sakura."
if [[ "$choice" == 'Local LLM (choose Qwen after setup)' ]]; then .venv-macos/bin/python startup_macos.py --setup-local; fi
/usr/bin/open "$wrapper"
'''

def udif(iso,destination):
    """Wrap an ISO9660/Rock Ridge volume in a raw UDIF disk image."""
    raw=iso.read_bytes(); assert len(raw)%512==0
    sectors=len(raw)//512;crc=zlib.crc32(raw)&0xffffffff
    table=bytearray(204)
    struct.pack_into('>4sIQQQII',table,0,b'mish',1,0,sectors,0,2048,0)
    struct.pack_into('>III',table,64,2,32,crc)
    struct.pack_into('>I',table,200,2)
    table+=struct.pack('>IIQQQQ',1,0,0,sectors,0,len(raw))
    table+=struct.pack('>IIQQQQ',0xffffffff,0,sectors,0,0,0)
    xml=plistlib.dumps({'resource-fork':{'blkx':[{'Attributes':'0x0050','Data':bytes(table),'ID':'0','Name':'Sakura Installer (ISO9660)'}]}})
    footer=bytearray(512)
    struct.pack_into('>4sIIIQQQQQII',footer,0,b'koly',4,512,1,0,0,len(raw),0,0,1,1)
    footer[64:80]=uuid.uuid4().bytes
    struct.pack_into('>III',footer,80,2,32,crc)
    struct.pack_into('>QQ',footer,216,len(raw),len(xml))
    struct.pack_into('>III',footer,352,2,32,zlib.crc32(struct.pack('>I',crc))&0xffffffff)
    struct.pack_into('>IQ',footer,488,2,sectors)
    destination.write_bytes(raw+xml+footer)

def macos():
    print('Building unsigned Apple Silicon bootstrap image…',flush=True)
    from PIL import Image
    import pycdlib
    package=BUILD/'mac'/f'{MAC_NAME}.app'/'Contents'
    resources=package/'Resources';(package/'MacOS').mkdir(parents=True,exist_ok=True);resources.mkdir(parents=True,exist_ok=True)
    Image.open(globals().get('APP_PNG',BASE/'static/assets/desktop-companion.png')).convert('RGBA').save(resources/'companion.icns',format='ICNS')
    with zipfile.ZipFile(resources/'source.zip','w',compression=zipfile.ZIP_DEFLATED) as output:
        for path,name in app_files():output.write(path,name)
        output.write(resources/'companion.icns','Sakura/launcher/companion.icns')
    (resources/'defaults.json').write_text(json.dumps(DEFAULTS,indent=2),encoding='utf-8')
    (resources/'install.command').write_text(MAC_INSTALL,encoding='utf-8',newline='\n')
    (package/'MacOS/Install').write_text('#!/bin/bash\nset -euo pipefail\n/usr/bin/open -a Terminal "$(dirname "$0")/../Resources/install.command"\n',encoding='utf-8',newline='\n')
    (package/'Info.plist').write_bytes(plistlib.dumps({'CFBundleExecutable':'Install','CFBundleName':MAC_NAME,'CFBundleIdentifier':'app.sakura.installer','CFBundlePackageType':'APPL','CFBundleIconFile':'companion.icns','LSMinimumSystemVersion':'14.0','NSHumanReadableCopyright':'SoulOfSwords'}))
    (BUILD/'mac/READ ME.txt').write_text('Sakura Companion — unsigned Apple Silicon bootstrap installer\n\nRequires macOS 14+, M1 or newer, internet. Open Sakura Installer.app.\nIt downloads native Python/dependencies. Local Qwen AI is optional.\nNo character, voice or Qwen models are included.\nInstalled app: ~/Applications/Sakura Companion.app\nApp data: ~/Library/Application Support/Sakura Companion/Sakura\nThis build was assembled on Windows; mounting and app execution must be verified on a Mac. It is not signed or notarized.\nIf Gatekeeper blocks it, use Finder right-click > Open or Privacy & Security > Open Anyway after reviewing the source.\n',encoding='utf-8')
    if MAC_README is not None:(BUILD/'mac/READ ME.txt').write_text(MAC_README,encoding='utf-8')
    image=pycdlib.PyCdlib();image.new(interchange_level=3,rock_ridge='1.09',vol_ident='SAKURA_INSTALLER')
    names={Path('.'):''};counter=0
    for path in sorted((BUILD/'mac').rglob('*'),key=lambda p:(len(p.parts),str(p))):
        relative=path.relative_to(BUILD/'mac');parent=names[relative.parent];counter+=1
        iso_name=parent+'/E'+str(counter).zfill(6)
        if path.is_dir():
            image.add_directory(iso_path=iso_name,rr_name=path.name);names[relative]=iso_name
        else:
            executable=path.suffix=='.command' or (len(relative.parts)>1 and relative.parts[-2]=='MacOS')
            image.add_file(str(path),iso_path=iso_name+';1',rr_name=path.name,file_mode=0o100755 if executable else 0o100644)
    iso=BUILD/'mac-installer.iso';image.write(str(iso));image.close()
    udif(iso,OUT/DMG_FILE)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--windows-only',action='store_true')
    parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--build-directory',type=Path,default=BUILD)
    args=parser.parse_args()
    OUT=args.output.resolve();BUILD=args.build_directory.resolve()
    OUT.mkdir(parents=True,exist_ok=True);BUILD.mkdir(parents=True,exist_ok=True)
    windows()
    if not args.windows_only:macos()
    checks={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in OUT.iterdir() if path.suffix in ('.exe','.dmg')}
    (OUT/'SHA256SUMS.txt').write_text('\n'.join(value+'  '+name for name,value in checks.items())+'\n')
    print(json.dumps(checks,indent=2))
