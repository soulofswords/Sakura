"""Source-free Windows core and obfuscated first-party browser modules."""
from pathlib import Path
import subprocess
import sys
import shutil
BASE=Path(__file__).resolve().parents[1]

def protected_asset_allowed(name):
    lowered=Path(name).name.lower()
    return not (lowered.endswith(('.bak','.backup','.orig','.rej','.tmp','.swp','.swo','.map','~')) or '.before-' in lowered)

def protected_files(records,output):
    records=[(path,name) for path,name in records if protected_asset_allowed(name)]
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    native=BASE/'tools/protected-build/native'
    subprocess.run([sys.executable,str(BASE/'tools/build-native-core.py')],check=True)
    core=next(native.glob('sakura_core*.pyd'))
    js_input=output/'js-input';js_output=output/'js';js_input.mkdir(exist_ok=True)
    for path,name in records:
        if name.startswith('Sakura/static/js/') and Path(name).suffix=='.js':shutil.copy2(path,js_input/Path(name).name)
    subprocess.run(['node',str(BASE/'tools/obfuscate-release.cjs'),str(js_input),str(js_output)],check=True)
    desktop=output/'desktop.py';desktop.write_text('import sakura_core\nfrom desktop import main\nmain()\n',encoding='utf-8')
    site=output/'sitecustomize.py';site.write_text('import sakura_core\n',encoding='utf-8')
    for path,name in records:
        if name.startswith('Sakura/') and name.count('/')==1 and name.endswith('.py'):continue
        if name.startswith('Sakura/static/js/') and Path(name).suffix=='.js':path=js_output/Path(name).name
        yield path,name
    yield core,'Sakura/'+core.name
    yield desktop,'Sakura/desktop.py'
    yield site,'Sakura/sitecustomize.py'
