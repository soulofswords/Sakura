"""Move clearly identified, standalone prop folders; never mixed avatar assets.

Defaults to a report. --apply requires a completed owner mirror/inventory audit.
Nothing is deleted, copied or shared; remote object keys remain the same.
"""
import argparse
import json
from pathlib import Path
import sys
from urllib.parse import quote,urlencode
from jio_library_owner import JioConnection,REGIONS

SAFE_PROP_NAMES={'musou isshin','vortex vanquisher','cannon','dorm','摩托','weapon','the portrait of markov'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    folder=Path(__file__).resolve().parents[2]/'private-model-library-pmx'
    inventory=json.loads((folder/'jio-source-inventory.json').read_text(encoding='utf-8'))['files']
    audit=json.loads((folder/'non-humanoid-audit.json').read_text(encoding='utf-8'))
    bad={x['path'] for x in audit['non_humanoid']};models={k for k in inventory if k.lower().endswith('.pmx')}
    candidates={x.rsplit('/',1)[0] for x in bad}
    selected=sorted(x for x in candidates if x.rsplit('/',1)[-1].casefold() in SAFE_PROP_NAMES
                    and {k for k in models if k.startswith(x+'/')}.issubset(bad))
    selected=[x for x in selected if not any(x.startswith(y+'/') for y in selected if x!=y)]
    report={'selected':selected,'moved':[],'ambiguous_left_in_place':sorted(candidates-set(selected))}
    if args.apply:
        owner=JioConnection();owner.resume();api='https://'+REGIONS[owner.session['dcGroupCode']]+'-api.jioaicloud.com'
        def listing(key):
            data=owner.request('GET',api+'/nms/metadata?'+urlencode({'limit':2000,'folderKey':key,'sort':'+objectName'}),authenticated=True)
            if data.get('nextLink'):raise ValueError('Folder listing requires pagination; no move attempted.')
            return data['objects']
        def child(key,name,create=False):
            rows=[x for x in listing(key) if x.get('objectName')==name and x.get('objectType')=='FR']
            if not rows and create:
                row=owner.request('POST',api+'/nms/folders',{'objectName':name,'parentObjectKey':key,'sourceName':'DRIVE'},authenticated=True)
                if row.get('parentObjectKey')!=key or row.get('objectName')!=name:raise ValueError('Folder creation was not confirmed.')
                return row
            if len(rows)!=1:raise ValueError('Folder missing or ambiguous: '+name)
            return rows[0]
        root=owner.session['rootFolderKey'];pmx=child(root,'PMX');tools=child(root,'Tools & Props',True)
        for relative in selected:
            parts=relative.split('/');source=pmx
            for name in parts:source=child(source['objectKey'],name)
            destination=tools
            for name in parts[:-1]:destination=child(destination['objectKey'],name,True)
            if any(x.get('objectName')==parts[-1] for x in listing(destination['objectKey'])):raise ValueError('Destination already exists; it was not overwritten.')
            before=source['parentObjectKey'];moved={**source,'parentObjectKey':destination['objectKey']}
            result=owner.request('PUT',api+'/nms/metadata/1.0',{'objects':[{'correlationId':owner.session['userId'],'operation':'MOVE','object':moved}]},authenticated=True)
            if result.get('unprocessed'):raise ValueError('Jio refused the folder move; review the owner report.')
            confirmed=owner.request('GET',api+'/nms/metadata/'+quote(source['objectKey'],safe='')+'/info',authenticated=True)
            if confirmed.get('parentObjectKey')!=destination['objectKey']:raise ValueError('Moved folder location could not be verified.')
            report['moved'].append({'source':'PMX/'+relative,'destination':'Tools & Props/'+relative,'objectKey':source['objectKey'],'previousParent':before})
            (folder/'jio-props-organization.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print('Moved standalone prop folder: '+relative,flush=True)
    (folder/'jio-props-organization.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'standalone_folders':len(selected),'moved':len(report['moved']),'deleted':0}),flush=True)

if __name__=='__main__':main()
