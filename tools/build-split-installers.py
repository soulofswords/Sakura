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
    if edition=='vtuber':
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
            source=replace(source,'mode.Items.AddRange(LocalLabels);' if name=='Installer.cs' else 'voice profiles', 'mode.Items.AddRange(new object[]{"VTuber tracking and model library"});' if name=='Installer.cs' else 'voice profiles')
            if name=='Installer.cs':
                source=replace(source,'if(local>0)Process.Start(new ProcessStartInfo(exe,"--setup-local "+LocalIds[local-1]){WorkingDirectory=target});\n   else if(launch.Checked)','if(launch.Checked)')
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
        rules='''#dance-btn,#dance-style,#dance-stop-btn,#chat-panel,#speech-bubble,#screen-view-btn,#screen-react-btn,#clear-memory-btn,#interrupt-btn,#vtuber-mode-btn,#auto-game-btn,#continuous-mic-btn,#tracking-restore-ai,#status-dot,#screen-audio-group,[data-tab="ai"],[data-tab="assistant"],#tab-ai,#tab-assistant{display:none!important}'''
    else:
        rules=''
    html=html.replace('</head>',f'<style>{rules}</style><script>window.SAKURA_EDITION={json.dumps(edition)};</script></head>')
    if edition=='vtuber':
        html=html.replace('/static/assets/desktop-companion.png','/static/assets/vtuber-app.png')
        html=html.replace('/static/assets/companion-vtuber.png','/static/assets/vtuber-app.png')
        html=html.replace('<strong>Sakura Companion</strong>','<strong>Sakura VTuber</strong>')
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
    builder.APP_ICON=BASE/'launcher'/('vtuber.ico' if edition=='vtuber' else 'companion.ico')
    builder.APP_PNG=BASE/'static/assets'/('vtuber-app.png' if edition=='vtuber' else 'desktop-companion.png')
    builder.INSTALLER_FILE=display.replace(' ','-')+'-Setup-Windows-x64.exe'
    builder.OUT=output;output.mkdir(parents=True,exist_ok=True);builder.BUILD=work/'build';builder.BUILD.mkdir()
    builder.DEFAULTS.update(vtuber_tracking_only=edition=='vtuber')
    builder.windows()
    if builder.PROTECT_RELEASE:
        print('Protected macOS native builds require a Mac build host; existing DMGs are unchanged.',flush=True)
        return builder,display
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
        'Kokoro speech voices are included. No character models, imported RVC weights or personal data are bundled.\n'
        'Windows build host: native Mac installation and camera operation are not tested.\n'
        'Not signed or notarized.\n')
    builder.macos()
    return builder,display

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=Path('C:/AI/Installer ready'));parser.add_argument('--edition',choices=['both','vtuber','companion'],default='both')
    args=parser.parse_args();reports=args.output/'split-build-reports';reports.mkdir(parents=True,exist_ok=True)
    root=BASE/'tools/edition-work';root.mkdir(exist_ok=True)
    try:
        subprocess.run([sys.executable,'-m','unittest','tests.test_installer_compression','-q'],cwd=BASE,check=True)
        subprocess.run([sys.executable,'-m','unittest','tests.test_companion_performance','tests.test_vtuber','tests.test_cloud_diagnostics','tests.test_mobile_models','-q'],cwd=BASE,check=True)
        subprocess.run(['node',str(BASE/'tests/color-dial.cjs')],cwd=BASE,check=True)
        subprocess.run(['node',str(BASE/'tests/tracking-backends.mjs')],cwd=BASE,check=True)
        subprocess.run([sys.executable,'-m','unittest','tests.test_product_editions','tests.test_startup_modes','tests.test_tracking_mode',
            'tests.test_model_import','tests.test_model_rig_validation','tests.test_native_model_picker','tests.test_native_clipboard','tests.test_pmx_editor','tests.test_texture_diagnostics','tests.test_model_repairs','tests.test_mobile_link','tests.test_voice_catalog','tests.test_voice','tests.test_speech_fallback','tests.test_kokoro_speech','tests.test_screen_audio','tests.test_dance_commands','tests.test_nvidia_ar_setup','tests.test_vbridger_receiver',
            'tests.test_agent_runtime','tests.test_agent_api','tests.test_agent_linkedin','tests.test_agent_calendar','tests.test_agent_mcp','tests.test_astra_strict','tests.test_normal_responses','tests.test_search_confirmation','tests.test_learned_answers','tests.test_local_clock','tests.test_chat_attachments','tests.test_medium_responses','tests.test_response_evidence','tests.test_factual_grounding','tests.test_hardware_metrics','tests.test_system_tools','tests.test_hindi_conversation','tests.test_reply_filler','tests.test_stt_commands','tests.test_persona_grounding','tests.test_shared_memory_claims','tests.test_session_greeting','tests.test_speech_decoration','tests.test_avatar_gestures','tests.test_direct_laugh','tests.test_game_laugh','tests.test_news_speech','tests.test_local_news','tests.test_app_branding','tests.test_pc_response_audit','tests.test_desktop_wake','tests.test_screen_snapshot','tests.test_chat_endpoint','tests.test_cloud_api','tests.test_companion_camera','tests.test_conversation_context_fix','tests.test_llm_context','tests.test_assistant_commands','tests.test_assistant_reminders','tests.test_assistant_updates','tests.test_weather_dates','tests.test_reaction_repeats','tests.test_reinstall_settings','tests.test_bytecode_build','tests.test_release_payload','tests.test_cursor_stream','tests.test_mobile_tls','tests.test_phone_permissions','tests.test_rvc_safe_load','-q'],cwd=BASE,check=True)
        for script in sorted((BASE/'static/js').glob('*.js')):subprocess.run(['node','--check',str(script)],check=True)
        subprocess.run(['node',str(BASE/'tests/render-budget.cjs')],cwd=BASE,check=True)
        subprocess.run(['node',str(BASE/'tests/live2d-controls.cjs')],cwd=BASE,check=True)
        subprocess.run([sys.executable,str(BASE/'tools/check-mobile-provider-errors.py')],cwd=BASE,check=True)
        subprocess.run([sys.executable,str(BASE/'tools/check-mobile-location.py')],cwd=BASE,check=True)
        subprocess.run([sys.executable,str(BASE/'tools/check-mobile-wake.py')],cwd=BASE,check=True)
        subprocess.run([sys.executable,str(BASE/'tools/check-wake-download.py')],cwd=BASE,check=True)
        for name in ['model-presentation.cjs','media-microphone.cjs','imported-greeting.cjs','game-laughter.cjs','app-branding.cjs','hand-presentation.cjs','screen-memory.cjs','avatar-preview.cjs','camera-preview.cjs','companion-camera.cjs','companion-camera-comments.cjs','assistant-reminders.cjs','mobile-link-controls.cjs','ai-vtuber-screen.cjs','game-mode.cjs','model-switching.cjs','model-controls-presentation.cjs','model-rig-monitor.cjs','model-repair-store.cjs','model-physics.cjs','physics-collisions.cjs',
            'reaction-expressions.cjs','auto-expressions.cjs','head-pose-filter.cjs','live2d-head-smooth.cjs','live2d-framing.cjs','vrm-framing.cjs','live2d-tracking-recovery.cjs','model-dance.cjs','expression-editor.cjs','expression-stacking.cjs','live2d-face-mapping.cjs','avatar-retarget.cjs','vrm-head-pitch.cjs','glasses-tracking.cjs','broadcast-camera.cjs','webcam-arm-rig.cjs','tracking-lifecycle.cjs','tracking-distance.cjs','tracking-distance-worker.cjs',
            'utility-request.cjs','desktop-wake-controls.cjs','voice-runtime.cjs','startup-presentation.cjs','live-screen.cjs','screen-mic-routing.cjs','screen-capture.cjs','screen-share.cjs','screen-audio.cjs','continuous-mic.cjs','speech-interrupt.cjs','speech-pipeline.cjs','texture-diagnostics.cjs','pmx-materials.cjs','pmx-nose-skin.cjs','vrm-gloss.cjs','opacity-boost.cjs','model-bones.cjs','pmx-layers.cjs','pmx-shaders.cjs','lip-sync.cjs','chat-reader-mouth.cjs','chat-reader-motion.cjs','voice-switching.cjs','post-speech-motion.cjs','direct-reply-reaction-pause.cjs','cursor-gpu-picking.cjs','cursor-stream.cjs','eye-tracking.cjs','model-drag-hit.cjs','part-appearance.cjs','stage-items.cjs','companion-studio-navigation.cjs','vtuber-studio-ui.cjs','mobile-appearance.cjs']:
            subprocess.run(['node',str(BASE/'tests'/name)],cwd=BASE,check=True)
        with tempfile.TemporaryDirectory(prefix='release-',dir=root) as temp:
            results=[]
            for edition in (['vtuber','companion'] if args.edition=='both' else [args.edition]):
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
