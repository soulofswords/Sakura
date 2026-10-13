"""One-command Windows release creation. Publish only after all checks pass."""
import argparse
from datetime import datetime
import hashlib
import importlib.metadata
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import traceback
import uuid

for stream in (sys.stdout,sys.stderr):
    if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')

BASE=Path(__file__).resolve().parents[1]

def pe_check(path):
    with path.open('rb') as source:
        header=source.read(64)
        if header[:2]!=b'MZ':raise ValueError('Output is not a Windows executable.')
        position=struct.unpack_from('<I',header,60)[0]
        source.seek(position);pe=source.read(24)
        if pe[:4]!=b'PE\0\0' or struct.unpack_from('<H',pe,4)[0]!=0x8664:
            raise ValueError('Output is not a valid x64 PE executable.')

def publish(artifact,destination,digest):
    """Stage on the destination drive before replacing the previous release."""
    import shutil
    pending=destination.with_name('.'+destination.name+'.building-'+uuid.uuid4().hex)
    try:
        with artifact.open('rb') as source,pending.open('xb') as target:
            shutil.copyfileobj(source,target,1024*1024);target.flush();os.fsync(target.fileno())
        if hashlib.sha256(pending.read_bytes()).hexdigest()!=digest:
            raise RuntimeError('Published copy failed checksum verification.')
        os.replace(pending,destination)
    finally:
        pending.unlink(missing_ok=True)

class Release:
    def __init__(self,output):
        self.output=output.resolve();self.output.mkdir(parents=True,exist_ok=True)
        self.reports=self.output/'build-reports';self.reports.mkdir(exist_ok=True)
        self.id=datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
        self.log=self.reports/('Build-'+self.id+'.md')
        self.stage='Preflight';self.entries=[];self.temp=None
        self.write('# Sakura Windows build\n\nRun: '+self.id+'\n\nProject: '+str(BASE)+'\n')
    def write(self,text):
        with self.log.open('a',encoding='utf-8') as output:output.write(text+'\n')
        print(text,flush=True)
    def run(self,label,args,cwd=BASE,timeout=900):
        self.stage=label;self.write('\n## '+label+'\n')
        environment=dict(os.environ,PYTHONUTF8='1',PYTHONUNBUFFERED='1')
        environment.pop('PYTHONOPTIMIZE',None) # Release verification assertions must run.
        try:
            result=subprocess.run([str(arg) for arg in args],cwd=cwd,env=environment,
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',timeout=timeout)
        except subprocess.TimeoutExpired as error:
            partial=error.stdout or ''
            if isinstance(partial,bytes):partial=partial.decode('utf-8',errors='replace')
            self.write('```text\n'+partial.replace('```','[code fence]')+'\nCommand timed out.\n```')
            raise
        self.write('```text\n'+result.stdout.replace('```','[code fence]')+'```')
        if result.returncode:raise RuntimeError(label+' failed (exit '+str(result.returncode)+'). See the build report for output.')
        self.entries.append(label)
    def preflight(self,build):
        if os.name!='nt':raise RuntimeError('Run this builder on Windows x64.')
        required=['tools/build-installers.py','tests/check_installer_artifacts.py',
                  'tests/installed_backend_smoke.py','launcher/Installer.cs',
                  'tools/packaging-cache/python-3.12.10-embed-amd64.zip']
        for name in required:
            if not (BASE/name).is_file():raise FileNotFoundError('Required build input missing: '+name)
        from packaging.requirements import Requirement
        for line in (BASE/'requirements.txt').read_text().splitlines():
            line=line.split('#',1)[0].strip()
            if not line:continue
            requirement=Requirement(line)
            if requirement.marker and not requirement.marker.evaluate():continue
            version=importlib.metadata.version(requirement.name)
            if requirement.specifier and version not in requirement.specifier:
                raise RuntimeError('Install the updated requirements in Sakura/venv before building: '+line)
        import py_compile
        for index,path in enumerate([*BASE.glob('*.py'),BASE/'tools/build-installers.py',Path(__file__)]):
            py_compile.compile(str(path),cfile=str(build/(str(index)+'.pyc')),doraise=True)
        self.write('Python syntax and installed application requirements: PASS')
        self.entries.append('Python syntax and requirements')
    def build(self):
        # Unique directories prevent an old smoke install from hiding missing package files.
        work=BASE/'tools/release-work';work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='build-',dir=work) as temporary:
            self.temp=Path(temporary)
            if not self.temp.resolve().is_relative_to(work.resolve()):
                raise RuntimeError('Temporary build path is outside the intended workspace.')
            stage=self.temp/'release';stage.mkdir();build=self.temp/'build';build.mkdir()
            self.preflight(build)
            snapshot=self.source_snapshot()
            self.run('Dependency consistency',[sys.executable,'-m','pip','check'])
            self.run('Startup and optional-download tests',[sys.executable,'-m','unittest',
                'tests.test_local_model_setup','tests.test_macos_startup_ui','tests.test_startup_modes','tests.test_windows_release_builder',
                'tests.test_tracking_mode','tests.test_vtuber','tests.test_vtuber_rvc_changer','tests.test_rvc_selection','tests.test_screen','tests.test_screen_snapshot','tests.test_chat_endpoint','tests.test_reaction_repeats','tests.test_reinstall_settings',
                'tests.test_model_import','tests.test_native_model_picker','tests.test_model_rig_validation','tests.test_voice_catalog','tests.test_bytecode_build','tests.test_spout_output','tests.test_companion_hotkey','tests.test_llm_context','-v'])
            import shutil
            node=shutil.which('node')
            if not node:raise RuntimeError('Node.js is required to validate the frontend. Install Node.js before building.')
            for script in sorted((BASE/'static/js').glob('*.js')):
                self.run('JavaScript syntax: '+script.name,[node,'--check',script],timeout=60)
            for name in ('model-switching.cjs','model-controls-presentation.cjs','model-rig-monitor.cjs','reaction-expressions.cjs','model-physics.cjs','model-humanoid.cjs','lip-sync.cjs','speech-pipeline.cjs','voice-switching.cjs','avatar-retarget.cjs','webcam-arm-rig.cjs','eye-tracking.cjs','hair-flexibility.cjs','tracking-lifecycle.cjs','reinstall-preferences.cjs','pmx-materials.cjs','pmx-layers.cjs','pmx-shaders.cjs','physics-drag-speech.cjs','physics-collisions.cjs','post-speech-motion.cjs','expression-editor.cjs','expression-stacking.cjs','live2d-expression.cjs','screen-capture.cjs','screen-share.cjs'):
                self.run('Frontend test: '+name,[node,BASE/'tests'/name],timeout=120)
            self.run('Compile current source and installer',[sys.executable,BASE/'tools/build-installers.py',
                '--windows-only','--output',stage,'--build-directory',build],timeout=1800)
            compiler=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
            stub=build/'check-stub.exe';chooser=build/'startup-check.exe'
            self.run('Compile launcher test fixture',[compiler,'/nologo','/out:'+str(stub),BASE/'tests/local-check-stub.cs'],timeout=120)
            self.run('Compile native chooser checks',[compiler,'/nologo','/reference:System.Windows.Forms.dll',
                '/reference:System.Drawing.dll','/out:'+str(chooser),BASE/'tests/launcher-startup.cs'],timeout=120)
            self.run('Native Gemini, Local and VTuber chooser checks',[chooser,build/'Desktop Companion.exe',BASE/'launcher/companion.ico',stub],timeout=120)
            contrast=build/'local-model-contrast.exe'
            self.run('Compile local-model contrast checks',[compiler,'/nologo','/reference:System.Windows.Forms.dll',
                '/reference:System.Drawing.dll','/out:'+str(contrast),BASE/'tests/local-model-contrast.cs'],timeout=120)
            self.run('Local-model enabled and disabled text rendering',[contrast,build/'Desktop Companion.exe',BASE/'launcher/companion.ico'],timeout=120)
            uninstall_check=build/'uninstall-check.exe'
            self.run('Compile uninstall checks',[compiler,'/nologo','/out:'+str(uninstall_check),BASE/'tests/uninstall-cleanup.cs'],timeout=120)
            self.run('Native uninstall cleanup and user-data preservation',[uninstall_check,build/'Uninstall.exe'],timeout=120)
            installer_ui=build/'installer-ui-check.exe'
            self.run('Compile installer UI checks',[compiler,'/nologo','/reference:System.Windows.Forms.dll',
                '/reference:System.Drawing.dll','/out:'+str(installer_ui),BASE/'tests/installer-ui.cs'],timeout=120)
            self.run('Native directory browser and automatic close checks',[installer_ui,stage/'Sakura-Setup-Windows-x64.exe'],timeout=120)
            reinstall=build/'installer-reinstall.exe'
            self.run('Compile reinstall checks',[compiler,'/nologo','/reference:System.Web.Extensions.dll',
                '/out:'+str(reinstall),BASE/'tests/installer-reinstall.cs'],timeout=120)
            self.run('Native installation detection and configuration merge',[reinstall,stage/'Sakura-Setup-Windows-x64.exe'],timeout=120)
            self.stage='Validate Windows executable';pe_check(stage/'Sakura-Setup-Windows-x64.exe')
            self.entries.append(self.stage)
            self.run('Payload integrity, installation and upgrade checks',[sys.executable,BASE/'tests/check_installer_artifacts.py',
                '--windows-only','--output',stage,'--build-directory',build],timeout=1200)
            installed=build/'smoke-install/Sakura';backend=installed/'backend-smoke.py'
            shutil.copy2(BASE/'tests/installed_backend_smoke.py',backend)
            self.run('Installed backend with no AI/models',[installed/'runtime/python.exe',backend],cwd=installed,timeout=120)
            self.stage='Compare packaged source with current project'
            if self.source_snapshot()!=snapshot:
                raise RuntimeError('Project source changed while tests/build were running. Save your changes and run the builder again.')
            # Catch edits made while packaging: never publish a mixture of source revisions.
            import importlib.util
            spec=importlib.util.spec_from_file_location('release_builder',BASE/'tools/build-installers.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            import zipfile
            with zipfile.ZipFile(build/'windows-payload.zip') as payload:
                for path,name in module.app_files():
                    if hashlib.sha256(path.read_bytes()).digest()!=hashlib.sha256(payload.read(name)).digest():
                        raise RuntimeError('Source changed during build: '+str(path)+'. Run the builder again after saving your changes.')
            self.entries.append(self.stage)
            self.stage='Publish verified installer'
            artifact=stage/'Sakura-Setup-Windows-x64.exe'
            digest=hashlib.sha256(artifact.read_bytes()).hexdigest()
            destination=self.output/artifact.name
            publish(artifact,destination,digest)
            # Keep the checksum entry for the existing Mac artifact, if present.
            hashes=[]
            for name in ('Sakura-Setup-Windows-x64.exe','Sakura-Setup-macOS-Apple-Silicon.dmg'):
                path=self.output/name
                if path.is_file():hashes.append(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+name)
            checksum=self.output/'SHA256SUMS.txt';pending=checksum.with_suffix('.tmp')
            pending.write_text('\n'.join(hashes)+'\n',encoding='utf-8');os.replace(pending,checksum)
            self.write('\n## Result\n\nPASS. Published: '+str(destination)+'\n\nSHA-256: `'+digest+'`\n\nChecks passed:\n\n'+'\n'.join('- '+entry for entry in self.entries)+'\n\nThe EXE is unsigned. Integrity checks do not certify a publisher identity.\nNo user character models, voice weights, Qwen weights, credentials or memory were bundled.\n')
            (self.output/'Build-Errors.md').write_text('# Latest Sakura build errors\n\nLatest build passed. No errors.\n\nReport: '+str(self.log)+'\n',encoding='utf-8')
            return destination
    def source_snapshot(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('snapshot_builder',BASE/'tools/build-installers.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        paths={path for path,_ in module.app_files()}
        paths.update((BASE/'launcher').glob('*.cs'))
        if (BASE/'tools/build_bytecode.py').exists(): paths.add(BASE/'tools/build_bytecode.py')
        paths.update((BASE/'tests').glob('*.py'))
        paths.update((BASE/'tests').glob('*.cjs'))
        paths.update((BASE/'tests').glob('*.cs'))
        paths.update((BASE/'tools').glob('*.py'))
        return {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    def failure(self,error):
        details='\n## Failure\n\nStage: '+self.stage+'\n\n```text\n'+traceback.format_exc().replace('```','[code fence]')+'\n```\n'
        self.write(details)
        report='# Sakura EXE build errors\n\nRun: '+self.id+'\n\nFailed stage: '+self.stage+'\n\n'+str(error)+'\n\nThe previous published EXE was not replaced unless publication had already completed.\n\nFull build output: '+str(self.log)+'\n'+details
        (self.reports/('Errors-'+self.id+'.md')).write_text(report,encoding='utf-8')
        (self.output/'Build-Errors.md').write_text(report,encoding='utf-8')

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('C:/AI/Installer ready'))
    args=parser.parse_args(argv)
    release=Release(args.output)
    lock=None
    try:
        import msvcrt
        lock=(BASE/'tools/.windows-release.lock').open('a+b')
        if lock.tell()==0:lock.write(b'0');lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        release.build();return 0
    except Exception as error:
        release.failure(error);return 1
    finally:
        if lock:lock.close()

if __name__=='__main__':sys.exit(main())
