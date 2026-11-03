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
import sys
from PIL import Image

BASE=Path(__file__).resolve().parents[1]
# mobile_tls lives at the repository root, and running this file as a script puts
# tools/ - not the root - on the import path.
sys.path.insert(0,str(BASE))
parser=argparse.ArgumentParser();parser.add_argument('--edition',choices=['combined','vtuber'],default='combined');parser.add_argument('--release-signing',action='store_true');args=parser.parse_args()
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
    res=BUILD/'res/drawable';res.mkdir(parents=True,exist_ok=True)
    (res/'icon.png').unlink(missing_ok=True) # obsolete generated drawable, never used by the new manifest
    Image.open(BASE/'android/assets/sakura-mobile-logo.png').convert('RGBA').resize((192,192),Image.Resampling.LANCZOS).save(res/'sakura_flower.png')
    run([tools/'aapt2.exe','compile','--dir',BUILD/'res','-o',BUILD/'resources.zip'])
    unsigned=BUILD/'unsigned.apk'
    run([tools/'aapt2.exe','link','-I',platform,'--manifest',source_root/'AndroidManifest.xml','--version-code','41','--version-name','2.0','--auto-add-overlay','-o',unsigned,BUILD/'resources.zip'])
    classes=BUILD/'classes';classes.mkdir(exist_ok=True)
    run([java/'javac.exe','-encoding','UTF-8','-source','8','-target','8','-classpath',os.pathsep.join(map(str,[platform,*wake_jars])),'-d',classes,*sorted((source_root/'src').rglob('*.java'))])
    classes_jar=BUILD/'classes.jar'
    with zipfile.ZipFile(classes_jar,'w') as archive:
        for path in classes.rglob('*.class'):archive.write(path,path.relative_to(classes).as_posix())
    dex=BUILD/'dex';dex.mkdir(exist_ok=True)
    run([java/'java.exe','-cp',tools/'lib/d8.jar','com.android.tools.r8.R8','--release','--pg-conf',source_root/'proguard-rules.pro','--lib',platform,'--min-api','28','--output',dex,classes_jar,*wake_jars])
    assets={}
    for path in (source_root/'assets').rglob('*'):
        if path.is_file() and path.suffix.lower() not in ('.bak','.map','.tmp','.orig'):assets[path]='assets/'+path.relative_to(source_root/'assets').as_posix()
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
    # Asserted before obfuscation for the same reason release-protection.py does it:
    # protected JavaScript hides implementation names inside an encoded string array.
    assert '_hitModelPixelAt' in (js_input/'model-viewer.js').read_text(encoding='utf-8'),'Bundled renderer lost the GPU pixel-picking implementation'
    run(['node',BASE/'tools/obfuscate-release.cjs',js_input,js_output])
    assets={(js_output/path.name if path.suffix=='.js' and not name.startswith('assets/static/vendor/') else path):name for path,name in assets.items()}
    with zipfile.ZipFile(unsigned,'a',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(dex/'classes.dex','classes.dex')
        for name,data in wake_native.items():archive.writestr(name,data)
        for path,name in assets.items():archive.write(path,name)
    aligned=BUILD/'aligned.apk'
    run([tools/'zipalign.exe','-f','-P','16','4',unsigned,aligned])
    keystore=CACHE/'testing-key.jks'
    alias='sakura'
    if args.release_signing:
        keystore=Path(os.environ.get('SAKURA_ANDROID_KEYSTORE',''))
        alias=os.environ.get('SAKURA_ANDROID_KEY_ALIAS','sakura')
        if not keystore.is_file() or not os.environ.get('SAKURA_ANDROID_STORE_PASSWORD') or not os.environ.get('SAKURA_ANDROID_KEY_PASSWORD'):
            raise RuntimeError('Release signing requires a private keystore and SAKURA_ANDROID_STORE_PASSWORD / SAKURA_ANDROID_KEY_PASSWORD environment variables. Never put them in source or command arguments.')
        storepass='env:SAKURA_ANDROID_STORE_PASSWORD';keypass='env:SAKURA_ANDROID_KEY_PASSWORD'
    else:
        print('TEST SIGNATURE: use --release-signing and a privately managed key for production distribution.',flush=True)
        if not keystore.exists():run([java/'keytool.exe','-genkeypair','-keystore',keystore,'-storepass','android','-keypass','android','-alias','sakura','-dname','CN=SoulOfSwords, O=Sakura','-keyalg','RSA','-keysize','2048','-validity','10000'])
        storepass=keypass='pass:android'
    from mobile_tls import restrict_private_key
    restrict_private_key(keystore)
    apk=OUT/('Sakura-VTuber-Mobile-Android.apk' if args.edition=='vtuber' else 'Sakura-Mobile-Android.apk')
    run([java/'java.exe','-jar',tools/'lib/apksigner.jar','sign','--ks',keystore,'--ks-key-alias',alias,'--ks-pass',storepass,'--key-pass',keypass,'--out',apk,aligned])
    run([java/'java.exe','-jar',tools/'lib/apksigner.jar','verify','--verbose',apk])
    run([tools/'aapt2.exe','dump','badging',apk])
    with zipfile.ZipFile(apk) as archive:
        assert archive.testzip() is None
        assert not any(n.lower().endswith(('.bak','.map','.tmp','.orig')) for n in archive.namelist()), 'Backup/debug source leaked into APK'
        for name in ('AndroidManifest.xml','classes.dex','assets/mobile.js','assets/static/vendor/tracking/face_landmarker.task'):assert name in archive.namelist()
        html_text=archive.read('assets/index.html').decode('utf-8')
        assert 'sakura-mobile-logo.png' in html_text and 'Settings → General' in html_text, 'Mobile branding or UI Unicode was corrupted during packaging'
        assert archive.read('assets/sakura-mobile-logo.png')==(application/'assets/sakura-mobile-logo.png').read_bytes(), 'Mobile logo missing or stale'
        assert not any(marker in html_text for marker in ('ðŸ','Â·','â†')), 'Garbled UI characters in APK'
        assert not any(name.endswith(('.pmx','.vrm','.moc3','.gguf','.mdl','.fst')) for name in archive.namelist()), 'No character/LLM/wake model packs in the APK'
        assert 'lib/arm64-v8a/libvosk.so' in archive.namelist() and 'assets/phone-wake.js' in archive.namelist()
        if args.edition=='combined':
            for name in ('assets/phone-local.js','assets/phone-avatar.js','assets/phone-stage.js','assets/phone-stage.css','assets/native-jobs.js','assets/static/js/model-viewer.js','assets/static/vendor/vrm/three-vrm.module.min.js','assets/static/vendor/live2d/cubism4.min.js','assets/static/vendor/live2d/unsafe-eval.min.js'):assert name in archive.namelist(),name
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
