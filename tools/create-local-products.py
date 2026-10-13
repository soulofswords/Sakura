"""Refresh the owner's two local apps without installers or copying model libraries."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

BASE=Path(__file__).resolve().parents[1]
ROOT=BASE.parent

def load(name,file):
    spec=importlib.util.spec_from_file_location(name,file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def main():
    split=load('split_local',BASE/'tools/build-split-installers.py')
    builder=load('package_local',BASE/'tools/build-installers.py')
    results=[]
    work=BASE/'tools/local-products';work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='refresh-',dir=work) as temp:
        for edition in ['vtuber','companion']:
            stage=Path(temp)/edition;stage.mkdir();display,launcher=split.edition_sources(edition,stage)
            destination=ROOT/display/'Sakura';destination.mkdir(parents=True,exist_ok=True)
            for path,name in builder.app_files():
                relative=Path(name).relative_to('Sakura');target=destination/relative
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
            shutil.copy2(stage/'index.html',destination/'static/index.html')
            shutil.copy2(stage/'product.json',destination/'product.json')
            editor_source=BASE/'tools/pmx-editor'
            if editor_source.is_dir():
                shutil.copytree(editor_source,destination/'tools/pmx-editor',dirs_exist_ok=True)
            if edition=='vtuber':
                source=(BASE/'static/js/app.js').read_text(encoding='utf-8')
                for old,new in [('Chat Reader off · AI remains paused','Chat Reader off · tracking is available'),('Unloading chat AI and speech models…','Preparing camera tracking…'),('Tracking off · AI remains paused','Tracking off'),('AI paused · choose your camera and start face, shoulder and arm tracking','Choose your camera and start face, shoulder and arm tracking')]:
                    source=split.replace(source,old,new)
                (destination/'static/js/app.js').write_text(source,encoding='utf-8')
            # Only seed user settings once. Refreshes must preserve edits made
            # in either separate app since its first launch.
            for name in ['settings.json','.gemini-key.bin','conversation-memory.json']:
                if edition=='vtuber' and name!='settings.json':continue
                original=BASE/name;target=destination/name
                if original.is_file() and not target.exists():shutil.copy2(original,target)
            settings=destination/'settings.json'
            if not settings.exists():settings.write_text(json.dumps(builder.DEFAULTS,indent=2),encoding='utf-8')
            # Directory junctions share large libraries/runtimes. Independent
            # desktop profiles and logs are deliberately not linked.
            for name in ['models','voices','venv','llm-models','ollama-runtime','rvc-assets','rvc-dependencies','rvc-extra','rvc-gpu-runtime','rvc-runtime','rvc-venv','rvc-amd-runtime']:
                if edition=='vtuber' and name in ['llm-models','ollama-runtime']:continue
                source=BASE/name;target=destination/name
                if not source.is_dir():continue
                if target.exists():
                    if not os.path.samefile(target,source):raise RuntimeError('Refusing to replace an existing independent directory: '+str(target))
                else:
                    subprocess.run(['powershell','-NoProfile','-Command',
                        'New-Item -ItemType Junction -Path '+"'"+str(target).replace("'","''")+"' -Target '"+str(source).replace("'","''")+"' | Out-Null"],check=True)
            launcher_source=(stage/'Launcher.cs').read_text(encoding='utf-8')
            launcher_source=split.replace(launcher_source,'string project=Path.Combine(root,"Sakura");',
                'string project=Path.Combine(root,"'+display+'","Sakura");')
            # Shared venv is used only to find the Python dependencies; create
            # an edition-specific branded interpreter alongside that runtime.
            (stage/'Launcher.cs').write_text(launcher_source,encoding='utf-8')
            builder.CS_DIR=stage
            built=stage/launcher;builder.compile_cs(built,['Launcher.cs','StartupDialog.cs','LocalModelDialog.cs'],['System.Web.Extensions'])
            try:shutil.copy2(built,ROOT/launcher)
            except PermissionError:
                pending=work/(launcher+'.pending');shutil.copy2(built,pending)
                updater=work/(edition+'-update.ps1')
                updater.write_text("$pending='"+str(pending).replace("'","''")+"'\n$target='"+str(ROOT/launcher).replace("'","''")+"'\nwhile(Test-Path -LiteralPath $pending){try{Copy-Item -LiteralPath $pending -Destination $target -Force -ErrorAction Stop;Remove-Item -LiteralPath $pending;break}catch{Start-Sleep -Seconds 3}}\n",encoding='utf-8')
                subprocess.Popen(['powershell','-NoProfile','-WindowStyle','Hidden','-File',str(updater)],creationflags=subprocess.CREATE_NO_WINDOW)
                print('Launcher is open; queued refresh for after it closes: '+launcher)
            subprocess.run([str(ROOT/launcher),'--check'],check=True)
            check='import app,product; assert product.EDITION=='+repr(edition)+'; assert app.get_settings()["product_edition"]=='+repr(edition)+'; print(product.DISPLAY_NAME+" local imports and product identity PASS")'
            subprocess.run([str(BASE/'venv/Scripts/python.exe'),'-c',check],cwd=destination,check=True)
            results.append({'product':display,'launcher':str(ROOT/launcher),'app':str(destination),'models':str((destination/'models').resolve())})
    # Preserve the old combined launcher as a recoverable developer artifact,
    # so the project root presents only the two new apps.
    old=ROOT/'Desktop Companion.exe'
    if old.exists():
        backup=BASE/'backups/combined-launcher-before-product-split';backup.mkdir(parents=True,exist_ok=True)
        saved=backup/old.name
        if not saved.exists():shutil.copy2(old,saved)
        try:old.unlink()
        except PermissionError:print('Old launcher is running; close it before removing its obsolete root copy.')
    (work/'Latest.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
