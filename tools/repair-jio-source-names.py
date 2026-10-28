"""Preserve missing original filenames in verified, same-folder repair archives."""
import argparse,hashlib,importlib.util,json,sys,tempfile,zipfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode
from jio_library_owner import private_directory

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--audit',type=Path,required=True);args=parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8');audit=json.loads(args.audit.read_text(encoding='utf-8'));base=Path(audit['localPath']).resolve()
    if audit['sizeMismatches'] or audit['hashMismatches'] or audit['duplicatePaths']:raise ValueError('Resolve source conflicts first.')
    groups=defaultdict(list)
    for name in audit['missing']:
        part=Path(name)
        if part.is_absolute() or '..' in part.parts:raise ValueError('Unsafe source path.')
        source=(base/part).resolve()
        if not source.is_relative_to(base) or not source.is_file():raise ValueError('Missing source changed.')
        if '__MACOSX' in part.parts or part.name in ('.DS_Store','Thumbs.db'):continue
        if source.suffix.lower() not in {'.txt','.md','.pdf','.tga','.png','.jpg','.jpeg','.bmp','.dds','.gif','.sph','.spa'}:raise ValueError('Unexpected source type.')
        groups[part.parent].append(source)
    spec=importlib.util.spec_from_file_location('jio_transfer',Path(__file__).with_name('upload-library-jio.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    work=private_directory()/'source-name-repairs';work.mkdir(parents=True,exist_ok=True);fixed=[]
    with tempfile.TemporaryDirectory(dir=work) as stage:
        transfer=module.JioUploader(stage);cache={}
        def listing(key):
            if key not in cache:
                _,data=transfer.request('GET',transfer.api+'/nms/metadata?'+urlencode({'limit':2000,'folderKey':key,'sort':'+objectName'}))
                if data.get('nextLink'):raise ValueError('Resolve paginated destination first.')
                cache[key]=data['objects']
            return cache[key]
        for relative,files in groups.items():
            key=transfer.connection.session['rootFolderKey']
            for component in [*audit['remotePath'].strip('/').split('/'),*relative.parts]:
                matches=[x for x in listing(key) if x.get('objectType')=='FR' and x.get('objectName','').casefold()==component.casefold()]
                if not matches:
                    _,created=transfer.request('POST',transfer.api+'/nms/folders',json_body={'objectName':component,'parentObjectKey':key,'sourceName':'DRIVE'})
                    if created.get('objectName')!=component or created.get('parentObjectKey')!=key:raise ValueError('Repair folder could not be verified.')
                    listing(key).append(created);matches=[created]
                if len(matches)!=1:raise ValueError('Ambiguous intended folder.')
                key=matches[0]['objectKey']
            fingerprint=hashlib.sha256()
            for source in sorted(files):fingerprint.update(source.name.encode()+b'\0'+source.read_bytes())
            archive=work/('Sakura-original-names-'+fingerprint.hexdigest()[:16]+'.zip')
            with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as package:
                for source in files:package.write(source,source.name)
            transfer.folder=key;transfer.remote={x['objectName']:[x] for x in listing(key) if x.get('objectType')!='FR'};transfer.assets={}
            transfer.ledger_path=work/('receipt-'+fingerprint.hexdigest()[:16]+'.json')
            receipt=transfer.upload_file(archive)
            if not receipt.get('verified'):raise ValueError('Archive verification failed.')
            fixed.extend({'path':(relative/source.name).as_posix(),'bytes':source.stat().st_size,'sha256':module.digest_file(source),'verified':True,'archive':archive.name} for source in files)
            (work/'verified-repairs.json').write_text(json.dumps(fixed,ensure_ascii=False,indent=2),encoding='utf-8')
            print('Original names preserved and download verified: '+str(relative)+' ('+str(len(files))+' files)',flush=True)
    print(json.dumps({'verified_files':len(fixed),'originals_unchanged':True}))

if __name__=='__main__':main()
