"""Delete only verified cloud-backed project models and obsolete generated caches.

Defaults to a concrete report. Never touches installed Companion/VTuber models,
unpublished originals, source code, credentials or current publication packages.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import stat

ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    with path.open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()

def linked(path,scope):
    current=path
    while current!=scope.parent:
        if current.is_symlink() or (hasattr(current,'is_junction') and current.is_junction()):return True
        current=current.parent
    return False

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8');private=ROOT.parent/'private-model-library-pmx'
    inventory=json.loads((private/'jio-source-inventory.json').read_text(encoding='utf-8'))['files']
    cloud={(int(x.get('sizeInBytes',0)),str(x.get('hash','')).lower()) for x in inventory.values() if isinstance(x.get('hash'),str) and len(x['hash'])==32}
    candidates=[];kept=[];model_root=ROOT/'models/pmx'
    # Entire immediate character/category folders must be backed up: no partial
    # texture deletion from an original that also contains unpublished assets.
    for category in sorted(model_root.iterdir()):
        if not category.is_dir() or linked(category,model_root):continue
        for folder in sorted(category.iterdir()):
            if not folder.is_dir() or linked(folder,model_root):continue
            files=[p for p in folder.rglob('*') if p.is_file()]
            if not files:continue
            verified=[]
            for path in files:
                if linked(path,model_root) or not path.resolve().is_relative_to(model_root.resolve()):break
                size=path.stat().st_size
                if not any(pair[0]==size for pair in cloud):break
                with path.open('rb') as source:md5=hashlib.file_digest(source,'md5').hexdigest()
                if (size,md5) not in cloud:break
                verified.append({'path':str(path.resolve()),'bytes':size,'sha256':sha(path),'scope':str(model_root.resolve()),'kind':'cloud-backed-project-pmx'})
            if len(verified)==len(files):candidates.extend(verified)
            else:kept.append({'folder':str(folder),'reason':'Contains files not verified in the Jio source inventory.'})
    prepared=json.loads((private/'prepared-models.json').read_text(encoding='utf-8'))
    assets=json.loads((private/'jio-uploaded-assets.json').read_text(encoding='utf-8'))['assets']
    current={key+extension for key in prepared for extension in ('.zip','.webp')}
    for name,receipt in assets.items():
        path=private/name
        if name in current or path.suffix not in ('.zip','.webp') or path.parent!=private or not path.is_file() or path.is_symlink():continue
        if not receipt.get('verified') or sha(path)!=receipt.get('sha256'):continue
        # Immutable files referenced by the current logical receipts are needed
        # for resume and are not obsolete cache.
        if any(value.get('remoteName')==name for key,value in assets.items() if key in current):continue
        candidates.append({'path':str(path.resolve()),'bytes':path.stat().st_size,'sha256':receipt['sha256'],'scope':str(private.resolve()),'kind':'obsolete-verified-package-cache'})
    for folder in [ROOT/'__pycache__',ROOT/'tests/__pycache__',ROOT/'tools/__pycache__',ROOT/'.pytest_cache']:
        if not folder.is_dir() or linked(folder,ROOT):continue
        for path in folder.rglob('*'):
            if path.is_file() and not linked(path,ROOT):candidates.append({'path':str(path.resolve()),'bytes':path.stat().st_size,'sha256':sha(path),'scope':str(folder.resolve()),'kind':'regenerable-python-cache'})
    unique={x['path']:x for x in candidates};candidates=list(unique.values())
    report={'planned_files':len(candidates),'planned_bytes':sum(x['bytes'] for x in candidates),'candidates':candidates,'kept_unverified':kept,'deleted_files':0,'deleted_bytes':0,'skipped_locked':[]}
    report_path=private/'project-cleanup-report.json';report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if args.apply:
        for entry in candidates:
            path=Path(entry['path']);scope=Path(entry['scope'])
            if not path.resolve().is_relative_to(scope) or linked(path,scope):raise ValueError('Cleanup target escaped its verified scope.')
            if not path.is_file() or path.stat().st_size!=entry['bytes'] or sha(path)!=entry['sha256']:raise ValueError('A cleanup target changed after inventory. It was not deleted.')
            try:
                if path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY:path.chmod(path.stat().st_mode|stat.S_IWRITE)
                path.unlink()
            except PermissionError:
                report['skipped_locked'].append(str(path));continue
            report['deleted_files']+=1;report['deleted_bytes']+=entry['bytes']
            if report['deleted_files']%100==0:report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        # Empty directories only, bottom-up; never recursive deletion/moving.
        for category in model_root.iterdir():
            if category.is_dir() and not linked(category,model_root):
                for folder in sorted((p for p in category.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):
                    if not linked(folder,model_root):
                        try:folder.rmdir()
                        except OSError:pass
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('planned_files','planned_bytes','deleted_files','deleted_bytes')}),flush=True)

if __name__=='__main__':main()
