"""Pinned Android wake libraries. Model pack downloads only after a phone user opts in."""
from pathlib import Path
import hashlib
import subprocess
import zipfile

ARTIFACTS = {
    'vosk': ('com/alphacephei/vosk-android/0.3.75/vosk-android-0.3.75.aar', 'ab2f8b91ac8051561aa325546b35fed9a68b36b8121bac5c6fb927525c4adfad'),
    'jna': ('net/java/dev/jna/jna/5.18.1/jna-5.18.1.aar', '7f053e3ec99e14dd71259c82c1c8a02738d64a13c31226b2acc170f3060951e0'),
}

def prepare(cache):
    cache=Path(cache)/'wake-deps';cache.mkdir(exist_ok=True)
    jars=[];native={}
    for name,(url,digest) in ARTIFACTS.items():
        archive=cache/(name+'.aar')
        if not archive.exists():
            # Native Windows TLS certificate verification remains enabled.
            subprocess.run(['powershell','-NoProfile','-Command',
                "Invoke-WebRequest -Uri 'https://repo1.maven.org/maven2/"+url+"' -OutFile '"+str(archive).replace("'","''")+"'"],check=True)
        if hashlib.sha256(archive.read_bytes()).hexdigest()!=digest:
            raise RuntimeError('Android wake dependency integrity check failed: '+name)
        folder=cache/name;folder.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            z.extract('classes.jar',folder);jars.append(folder/'classes.jar')
            for item in z.namelist():
                if item.startswith('jni/') and item.endswith('.so') and item.split('/')[1] in ('arm64-v8a','armeabi-v7a','x86','x86_64'):
                    native['lib/'+item[4:]]=z.read(item)
    return jars,native
