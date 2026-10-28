"""Repair published browsing metadata without repacking or editing any models."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model_library_paths import pmx_library_name
from jio_library_owner import private_directory


def repair(directory, apply=False):
    directory=Path(directory)
    inventory=json.loads((directory/'jio-source-inventory.json').read_text(encoding='utf-8'))
    siblings=Counter(str(Path(path).parent) for path in inventory['files'] if path.lower().endswith('.pmx'))
    checkpoint=directory/'prepared-models.json'
    prepared=json.loads(checkpoint.read_text(encoding='utf-8'));changes=[]
    for entry in prepared.values():
        source=entry.get('variant_model') or entry.get('preview_model','').removeprefix('pmx/')
        if not source:continue
        name=pmx_library_name(source,siblings[str(Path(source).parent)]>1)
        if len(name)>200:raise ValueError('A full model path exceeds the current catalogue limit; keep the old metadata and review it.')
        if name!=entry['name']:
            changes.append({'id':entry['id'],'before':entry['name'],'after':name});entry['name']=name
    if apply and changes:
        shutil.copy2(checkpoint,directory/f'prepared-models.before-hierarchy-{time.time_ns()}.json')
        temporary=checkpoint.with_suffix('.hierarchy-tmp');temporary.write_text(json.dumps(prepared,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(checkpoint)
    report={'changed':len(changes),'applied':apply,'changes':changes}
    (directory/'folder-hierarchy-repair.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    result=repair(private_directory('pmx'),args.apply)
    print(json.dumps({key:value for key,value in result.items() if key!='changes'}))
