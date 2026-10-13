"""Create separately branded, isolated VTuber and Companion releases."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser

BASE=Path(__file__).resolve().parents[1]

def replace(source,old,new):
    if old not in source:raise ValueError('Release template changed; missing: '+old[:90])
    return source.replace(old,new)

class VTuberHtml(HTMLParser):
    """Keep control IDs for shared event handlers, remove assistant wording."""
    def __init__(self):super().__init__(convert_charrefs=False);self.output=[]
    def clean(self,text):
        text=text.replace('Chat AI, speech and screen reactions are paused and the local language model is unloaded.','')
        text=text.replace('No AI replies.','').replace('without speaking or loading AI','without playing audio')
        text=text.replace('AI companion','window').replace('AI VTuber','Stream co-host')
        return re.sub(r'\bAI\b','',text)
    def handle_starttag(self,tag,attrs):
        from html import escape
        self.output.append('<'+tag+''.join(' '+k+(('="'+escape(self.clean(v) if k in ('title','aria-label') else v,quote=True)+'"') if v is not None else '') for k,v in attrs)+'>')
    def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs)
    def handle_endtag(self,tag):self.output.append('</'+tag+'>')
    def handle_data(self,data):self.output.append(self.clean(data))
    def handle_entityref(self,name):self.output.append('&'+name+';')
    def handle_charref(self,name):self.output.append('&#'+name+';')
    def handle_decl(self,decl):self.output.append('<!'+decl+'>')
    def handle_comment(self,data):pass

def edition_sources(edition,stage):
    display='Sakura VTuber' if edition=='vtuber' else 'Sakura Companion'
    launcher=display+'.exe'
    source=(BASE/'launcher/Launcher.cs').read_text(encoding='utf-8-sig')
    source=source.replace('Desktop Companion',display)
    if edition=='vtuber':
        source=source.replace('Sakura Companion','Sakura VTuber')
        begin=source.index(' static string ChooseMode(');end=source.index(' [STAThread]',begin)
        source=source[:begin]+''' static string ChooseMode(string project,out string key){key="";return "vtuber";}
 static string PythonPath(string project){foreach(string candidate in new[]{Path.Combine(project,"venv","Scripts","python.exe"),Path.Combine(project,"runtime","python.exe")})if(File.Exists(candidate))return candidate;return "";}
'''+source[end:]
        source=source.replace('LocalModelDialog.Python(project)','PythonPath(project)')
        begin=source.index('    if(args.Length>0&&args[0]=="--setup-local")');end=source.index('    string key;',begin)
        source=source[:begin]+source[end:]
    (stage/'Launcher.cs').write_text(source,encoding='utf-8')
    startup=(BASE/'launcher/StartupDialog.cs').read_text(encoding='utf-8-sig')
    if edition=='companion':
        startup=replace(startup,'for(int i=0;i<3;i++) {','for(int i=0;i<modes.Length;i++) {')
    else:
        startup='// Tracking launcher does not use a startup chooser.\n'
    (stage/'StartupDialog.cs').write_text(startup,encoding='utf-8')
    (stage/'LocalModelDialog.cs').write_text((BASE/'launcher/LocalModelDialog.cs').read_text(encoding='utf-8-sig') if edition=='companion' else '// No local language model downloader in the tracking launcher.\n',encoding='utf-8')
    installer=(BASE/'launcher/Installer.cs').read_text(encoding='utf-8-sig')
    uninstaller=(BASE/'launcher/Uninstall.cs').read_text(encoding='utf-8-sig')
    for name,source in [('Installer.cs',installer),('Uninstall.cs',uninstaller)]:
        source=source.replace('Desktop Companion.exe',launcher)
        if edition=='vtuber':
            source=source.replace('Sakura Companion',display).replace('SakuraCompanion','SakuraVTuber')
            source=source.replace('downloaded AI','voice profiles')
            source=source.replace('No character, voice or AI models are bundled. Import your own later.','Import your own character models and voice profiles after installation.')
            source=source.replace('Optional local AI (downloads after installation)','Face tracking, hand tracking and streaming tools')
            source=replace(source,'mode.Items.AddRange(new object[]{"Gemini API key — skip local AI download","Qwen 2B — 8 GB RAM / 4 GB VRAM recommended","Qwen 4B — 16 GB RAM / 6–8 GB VRAM recommended"});' if name=='Installer.cs' else 'voice profiles', 'mode.Items.AddRange(new object[]{"VTuber tracking and model library"});' if name=='Installer.cs' else 'voice profiles')
            if name=='Installer.cs':
                source=replace(source,'if(local>0)Process.Start(new ProcessStartInfo(exe,"--setup-local "+(local==1?"2b":"4b")){WorkingDirectory=target});\n   else if(launch.Checked)','if(launch.Checked)')
        if name=='Installer.cs':
            # Do not allow one product's update to overwrite the other product.
            source=replace(source,'  Directory.CreateDirectory(directory);',f'''  string marker=Path.Combine(directory,".sakura-installation");
  if(File.Exists(marker)&&File.ReadAllText(marker).Trim()!="{display} installation v1")throw new IOException("This folder belongs to another Sakura product. Choose a separate install folder.");
  Directory.CreateDirectory(directory);''')
        (stage/name).write_text(source,encoding='utf-8')
    html=(BASE/'static/index.html').read_text(encoding='utf-8-sig')
    if edition=='vtuber':
        parser=VTuberHtml();parser.feed(html);html=''.join(parser.output)
        html=html.replace('<title>Sakura — Anime  Assistant</title>','<title>Sakura VTuber</title>')
        rules='''#dance-btn,#dance-style,#dance-stop-btn,#chat-panel,#speech-bubble,#screen-view-btn,#screen-react-btn,#clear-memory-btn,#interrupt-btn,#vtuber-mode-btn,#auto-game-btn,#continuous-mic-btn,#tracking-restore-ai,#status-dot,[data-tab="ai"],[data-tab="assistant"],#tab-ai,#tab-assistant{display:none!important}'''
    else:
        rules=''
    html=html.replace('</head>',f'<style>{rules}</style><script>window.SAKURA_EDITION={json.dumps(edition)};</script></head>')
    (stage/'index.html').write_text(html,encoding='utf-8')
    (stage/'product.json').write_text(json.dumps({'edition':edition,'display_name':display}),encoding='utf-8')
    return display,launcher

def build_edition(edition,output,work):
    spec=importlib.util.spec_from_file_location('installer_builder',BASE/'tools/build-installers.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    stage=work/'sources';stage.mkdir(parents=True)
    display,launcher=edition_sources(edition,stage)
    originals=list(builder.app_files())
    app_js=(BASE/'static/js/app.js').read_text(encoding='utf-8-sig')
    if edition=='vtuber':
        for old,new in [('Chat Reader off · AI remains paused','Chat Reader off · tracking is available'),('Unloading chat AI and speech models…','Preparing camera tracking…'),('Tracking off · AI remains paused','Tracking off'),('AI paused · choose your camera and start face, shoulder and arm tracking','Choose your camera and start face, shoulder and arm tracking')]:
            app_js=replace(app_js,old,new)
    (stage/'app.js').write_text(app_js,encoding='utf-8')
    mac_start=(BASE/'startup_macos.py').read_text(encoding='utf-8')
    if edition=='vtuber':
        mac_start="import os,sys\nfrom pathlib import Path\nos.environ['SAKURA_START_MODE']='vtuber'\nos.execv(sys.executable,[sys.executable,str(Path(__file__).parent/'desktop.py')])\n"
    (stage/'startup_macos.py').write_text(mac_start,encoding='utf-8')
    def files():
        for path,name in originals:
            replacement={'Sakura/static/index.html':stage/'index.html','Sakura/static/js/app.js':stage/'app.js'}
            yield replacement.get(name,path),name
        yield stage/'product.json','Sakura/product.json'
    builder.app_files=files;builder.CS_DIR=stage;builder.LAUNCHER_FILE=launcher
    builder.INSTALLER_FILE=display.replace(' ','-')+'-Setup-Windows-x64.exe'
    builder.OUT=output;output.mkdir(parents=True,exist_ok=True);builder.BUILD=work/'build';builder.BUILD.mkdir()
    builder.DEFAULTS.update(vtuber_tracking_only=edition=='vtuber')
    builder.windows()
    # macOS gets its own edition startup; Windows keeps source/bytecode exact.
    windows_files=builder.app_files
    def mac_files():
        for path,name in windows_files():yield (stage/'startup_macos.py' if name=='Sakura/startup_macos.py' else path),name
    builder.app_files=mac_files
    builder.MAC_NAME=display+' Installer';builder.DMG_FILE=display.replace(' ','-')+'-Setup-macOS-Apple-Silicon.dmg'
    script=builder.MAC_INSTALL.replace('Sakura Companion',display).replace('app.sakura.companion','app.sakura.'+edition)
    if edition=='vtuber':
        script=re.sub(r'^choice=\$\(.*$', 'choice=tracking',script,flags=re.M)
        script=re.sub(r'^if \[\[ "\$choice" == \'Local LLM.*$', '',script,flags=re.M)
        script=script.replace('"$project/llm-models/blobs" "$project/llm-models/manifests"','')
    builder.MAC_INSTALL=script
    builder.MAC_README=(display+' — Apple Silicon bootstrap installer\n\nRequires macOS 14+, M1 or newer and internet for dependency setup.\n'
        'No character models, voice weights or personal data are bundled.\n'
        'Windows build host: native Mac installation and camera operation are not tested.\n'
        'Not signed or notarized.\n')
    builder.macos()
    return builder,display

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=Path('C:/AI/Installer ready'))
    args=parser.parse_args();reports=args.output/'split-build-reports';reports.mkdir(parents=True,exist_ok=True)
    root=BASE/'tools/edition-work';root.mkdir(exist_ok=True)
    try:
        subprocess.run([sys.executable,'-m','unittest','tests.test_product_editions','tests.test_startup_modes','tests.test_tracking_mode',
            'tests.test_model_import','tests.test_model_rig_validation','tests.test_native_model_picker','tests.test_voice_catalog','tests.test_dance_commands','tests.test_nvidia_ar_setup',
            'tests.test_screen_snapshot','tests.test_chat_endpoint','tests.test_reinstall_settings','tests.test_bytecode_build','-q'],cwd=BASE,check=True)
        for script in sorted((BASE/'static/js').glob('*.js')):subprocess.run(['node','--check',str(script)],check=True)
        for name in ['model-switching.cjs','model-controls-presentation.cjs','model-rig-monitor.cjs','model-physics.cjs','physics-collisions.cjs',
            'reaction-expressions.cjs','model-dance.cjs','expression-editor.cjs','expression-stacking.cjs','live2d-face-mapping.cjs','avatar-retarget.cjs','glasses-tracking.cjs','broadcast-camera.cjs','webcam-arm-rig.cjs','tracking-lifecycle.cjs','tracking-distance.cjs','tracking-distance-worker.cjs',
            'pmx-materials.cjs','pmx-layers.cjs','pmx-shaders.cjs','lip-sync.cjs','voice-switching.cjs','post-speech-motion.cjs']:
            subprocess.run(['node',str(BASE/'tests'/name)],cwd=BASE,check=True)
        with tempfile.TemporaryDirectory(prefix='release-',dir=root) as temp:
            results=[]
            for edition in ['vtuber','companion']:
                display='Sakura VTuber' if edition=='vtuber' else 'Sakura Companion'
                work=Path(temp)/edition;work.mkdir();out=work/'release'
                builder,_=build_edition(edition,out,work)
                check=work/'edition-check.exe'
                subprocess.run([str(builder.CSC),'/nologo','/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll','/reference:System.Web.Extensions.dll','/out:'+str(check),str(BASE/'tests/edition-installer.cs')],check=True)
                installed=work/'smoke-install'
                subprocess.run([str(check),str(out/builder.INSTALLER_FILE),str(installed),edition],check=True)
                project=installed/'Sakura';shutil.copy2(BASE/'tests/edition_backend_smoke.py',project/'edition_backend_smoke.py')
                subprocess.run([str(project/'runtime/python.exe'),str(project/'edition_backend_smoke.py'),edition],cwd=project,check=True)
                for path in [*out.glob('*.exe'),*out.glob('*.dmg')]:
                    target=args.output/display/path.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
                    results.append({'product':display,'file':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
            (reports/'Latest.md').write_text('# Separate product installers\n\nPASS: installation, update, settings, payload integrity and edition backend isolation.\n\n'+json.dumps(results,indent=2),encoding='utf-8')
            print(json.dumps(results,indent=2))
    except Exception:
        import traceback
        (reports/'Errors.md').write_text('# Split build error\n\n```\n'+traceback.format_exc()+'\n```',encoding='utf-8');raise

if __name__=='__main__':main()
