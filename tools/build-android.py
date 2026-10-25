"""Build a signed testing APK using downloaded Android 35 tools and JDK 17."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import zipfile
import argparse
import runpy
import re
from PIL import Image

BASE=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--edition',choices=['combined','vtuber'],default='combined');args=parser.parse_args()
# Keep old automation arguments compatible; mobile is now one combined product.
if args.edition=='vtuber':
    print('Sakura VTuber Mobile has merged into Sakura Mobile; building the combined APK.',flush=True)
    args.edition='combined'
CACHE=BASE/'tools/android-cache';BUILD=CACHE/('build-vtuber' if args.edition=='vtuber' else 'build');BUILD.mkdir(parents=True,exist_ok=True)
OUT=Path('C:/AI/Installer ready')/('Sakura VTuber Mobile' if args.edition=='vtuber' else 'Sakura Mobile');OUT.mkdir(parents=True,exist_ok=True)
def run(args):subprocess.run([str(a) for a in args],check=True,env=ENV)
try:
    java=next((CACHE/'jdk').rglob('javac.exe')).parent
    tools=next((CACHE/'build-tools').rglob('aapt2.exe')).parent
    platform=next((CACHE/'platform').rglob('android.jar'))
    ENV={**os.environ,'JAVA_HOME':str(java.parent),'PATH':str(java)+os.pathsep+os.environ['PATH']}
    wake_jars,wake_native=runpy.run_path(str(BASE/'tools/android-wake-deps.py'))['prepare'](CACHE)
    application=BASE/'android';source_root=application
    if args.edition=='vtuber':
        source_root=BUILD/'edition';shutil.copytree(application,source_root,dirs_exist_ok=True)
        manifest=source_root/'AndroidManifest.xml';manifest.write_text(manifest.read_text(encoding='utf-8').replace('app.sakura.mobile','app.sakura.vtubermobile').replace('Sakura Mobile','Sakura VTuber Mobile'),encoding='utf-8')
        content=manifest.read_text(encoding='utf-8')
        content=re.sub(r'\s*<uses-permission android:name="(?:android.permission.(?:CALL_PHONE|READ_CONTACTS|READ_PHONE_STATE|RECORD_AUDIO|ACCESS_COARSE_LOCATION|ACCESS_FINE_LOCATION)|com.android.alarm.permission.SET_ALARM)"/>','',content)
        manifest.write_text(content,encoding='utf-8')
        rules=source_root/'proguard-rules.pro';rules.write_text(rules.read_text(encoding='utf-8').replace('app.sakura.mobile','app.sakura.vtubermobile'),encoding='utf-8')
        for java_source in (source_root/'src').rglob('*.java'):
            content=java_source.read_text(encoding='utf-8').replace('package app.sakura.mobile;','package app.sakura.vtubermobile;').replace('/(state|command|frame|camera|chat|gemini)','/(state|command|frame)').replace('localAvailable=true','localAvailable=false')
            java_source.write_text(content,encoding='utf-8')
        html=source_root/'assets/index.html';content=html.read_text(encoding='utf-8').replace('Sakura Mobile','Sakura VTuber Mobile').replace('expression controls and companion chat','expression controls')
        content=re.sub(r'<button data-tab="companion">.*?</button>','',content)
        content=re.sub(r'<section id="companion">[\s\S]*?</section>','',content)
        content=re.sub(r'<section id="phone-camera-section">[\s\S]*?</section>','',content)
        content=re.sub(r'<!-- LOCAL-START -->[\s\S]*?<!-- LOCAL-END -->','',content)
        content=content.replace('Your character, on PC or on your phone.','One character. PC rendering. Phone controls.')
        html.write_text(content,encoding='utf-8')
        script=source_root/'assets/mobile.js';content=script.read_text(encoding='utf-8').replace("['companion','expression','vtuber']","['expression','vtuber']")
        content=re.sub(r"^\$\('(?:gemini|send)'\)\.onclick=.*$",'',content,flags=re.M)
        content=content.replace("if(data.edition==='vtuber')document.querySelector('[data-tab=\"expression\"]').click();","document.querySelector('[data-tab=\"expression\"]').click();")
        script.write_text(content,encoding='utf-8')
    res=BUILD/'res/drawable';res.mkdir(parents=True,exist_ok=True)
    (res/'icon.png').unlink(missing_ok=True) # obsolete generated drawable, never used by the new manifest
    Image.open(BASE/'static/assets/desktop-companion.png').convert('RGBA').resize((192,192)).save(res/'sakura_flower.png')
    run([tools/'aapt2.exe','compile','--dir',BUILD/'res','-o',BUILD/'resources.zip'])
    unsigned=BUILD/'unsigned.apk'
    run([tools/'aapt2.exe','link','-I',platform,'--manifest',source_root/'AndroidManifest.xml','--version-code','35','--version-name','0.3.29','--auto-add-overlay','-o',unsigned,BUILD/'resources.zip'])
    classes=BUILD/'classes';classes.mkdir(exist_ok=True)
    run([java/'javac.exe','-encoding','UTF-8','-source','8','-target','8','-classpath',os.pathsep.join(map(str,[platform,*wake_jars])),'-d',classes,*sorted((source_root/'src').rglob('*.java'))])
    classes_jar=BUILD/'classes.jar'
    with zipfile.ZipFile(classes_jar,'w') as archive:
        for path in classes.rglob('*.class'):archive.write(path,path.relative_to(classes).as_posix())
    dex=BUILD/'dex';dex.mkdir(exist_ok=True)
    run([java/'java.exe','-cp',tools/'lib/d8.jar','com.android.tools.r8.R8','--release','--pg-conf',source_root/'proguard-rules.pro','--lib',platform,'--min-api','28','--output',dex,classes_jar,*wake_jars])
    assets={}
    for path in (source_root/'assets').rglob('*'):
        if path.is_file() and path.suffix.lower() not in ('.bak','.map','.tmp','.orig') and not (args.edition=='vtuber' and path.name in ('phone-local.js','phone-avatar.js','phone-stage.js','phone-stage.css','local-viewer.html','local-setup.js','provider-tools.js')):assets[path]='assets/'+path.relative_to(source_root/'assets').as_posix()
    if args.edition=='combined':
        for path in (BASE/'static/js').rglob('*.js'):assets[path]='assets/static/js/'+path.relative_to(BASE/'static/js').as_posix()
        for path in (BASE/'static/vendor').rglob('*'):
            if path.is_file():assets[path]='assets/static/vendor/'+path.relative_to(BASE/'static/vendor').as_posix()
    for folder in ('static/assets/animations','static/audio/reactions'):
        for path in (BASE/folder).rglob('*'):
            if path.is_file():assets[path]='assets/'+path.relative_to(BASE).as_posix()
    for name in ('avatar-tracking.js','head-pose-filter.js','avatar-tracking-worker.js','tracking-distance.js','button-feedback.js'):
        assets[BASE/'static/js'/name]='assets/static/js/'+name
    for path in (BASE/'static/vendor/tracking').rglob('*'):
        if path.is_file():assets[path]='assets/static/vendor/tracking/'+path.relative_to(BASE/'static/vendor/tracking').as_posix()
    assets[BASE/'static/vendor/three/build/three.module.js']='assets/static/vendor/three/build/three.module.js'
    assets[BASE/'static/vendor/three/LICENSE']='assets/static/vendor/three/LICENSE'
    js_input=BUILD/'js-input';js_output=BUILD/'js-protected';js_input.mkdir(exist_ok=True)
    for path,name in assets.items():
        if path.suffix=='.js' and not name.startswith('assets/static/vendor/'):
            shutil.copy2(path,js_input/path.name)
    run(['node',BASE/'tools/obfuscate-release.cjs',js_input,js_output])
    assets={(js_output/path.name if path.suffix=='.js' and not name.startswith('assets/static/vendor/') else path):name for path,name in assets.items()}
    with zipfile.ZipFile(unsigned,'a',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(dex/'classes.dex','classes.dex')
        for name,data in wake_native.items():archive.writestr(name,data)
        for path,name in assets.items():archive.write(path,name)
    aligned=BUILD/'aligned.apk'
    run([tools/'zipalign.exe','-f','-P','16','4',unsigned,aligned])
    keystore=CACHE/'testing-key.jks'
    if not keystore.exists():run([java/'keytool.exe','-genkeypair','-keystore',keystore,'-storepass','android','-keypass','android','-alias','sakura','-dname','CN=SoulOfSwords, O=Sakura','-keyalg','RSA','-keysize','2048','-validity','10000'])
    apk=OUT/('Sakura-VTuber-Mobile-Android.apk' if args.edition=='vtuber' else 'Sakura-Mobile-Android.apk')
    run([java/'java.exe','-jar',tools/'lib/apksigner.jar','sign','--ks',keystore,'--ks-key-alias','sakura','--ks-pass','pass:android','--key-pass','pass:android','--out',apk,aligned])
    run([java/'java.exe','-jar',tools/'lib/apksigner.jar','verify','--verbose',apk])
    run([tools/'aapt2.exe','dump','badging',apk])
    with zipfile.ZipFile(apk) as archive:
        assert archive.testzip() is None
        assert not any(n.lower().endswith(('.bak','.map','.tmp','.orig')) for n in archive.namelist()), 'Backup/debug source leaked into APK'
        for name in ('AndroidManifest.xml','classes.dex','assets/mobile.js','assets/static/vendor/tracking/face_landmarker.task'):assert name in archive.namelist()
        html_text=archive.read('assets/index.html').decode('utf-8')
        assert '🌸 Sakura' in html_text and 'Settings → General' in html_text, 'UI Unicode was corrupted during packaging'
        assert not any(marker in html_text for marker in ('ðŸ','Â·','â†')), 'Garbled UI characters in APK'
        assert not any(name.endswith(('.pmx','.vrm','.moc3','.gguf','.mdl','.fst')) for name in archive.namelist()), 'No character/LLM/wake model packs in the APK'
        assert 'lib/arm64-v8a/libvosk.so' in archive.namelist() and 'assets/phone-wake.js' in archive.namelist()
        if args.edition=='combined':
            for name in ('assets/phone-local.js','assets/phone-avatar.js','assets/phone-stage.js','assets/phone-stage.css','assets/native-jobs.js','assets/static/js/model-viewer.js','assets/static/vendor/vrm/three-vrm.module.min.js','assets/static/vendor/live2d/cubism4.min.js'):assert name in archive.namelist(),name
            assert '<option value="female">Female</option>' in html_text and '<option value="male">Male</option>' in html_text
        else:
            assert 'id="local-mode"' not in html_text
            assert 'assets/phone-local.js' not in archive.namelist()
    (OUT/'Build.md').write_text('# Sakura Mobile testing APK\n\nPASS: Java compilation, R8 release shrink/obfuscation, obfuscated app JavaScript, resources, APK signature verification and archive integrity.\nNo irreversible-encryption claim.\n\nSHA256: '+hashlib.sha256(apk.read_bytes()).hexdigest()+'\n\nAndroid 9+; current Android System WebView required. Signed with a local testing key. Native phone camera and home-network behavior still require a physical-device test.\n',encoding='utf-8')
    print('APK READY:',apk)
except Exception:
    import traceback
    (OUT/'Errors.md').write_text('# Android build error\n\n```\n'+traceback.format_exc()+'\n```',encoding='utf-8')
    raise
