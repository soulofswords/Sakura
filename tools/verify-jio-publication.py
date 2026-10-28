"""Owner-only authenticated catalogue, preview and temporary-install verification."""
import io
import json
from pathlib import Path
import sys
import tempfile
import time

def verify(root=None):
    root=Path(root or Path(__file__).resolve().parents[1]);installed=root.parent/'Sakura Companion/Sakura'
    sys.path.insert(0,str(installed if installed.is_dir() else root))
    import requests
    from agent_connections import secret_get,secret_set
    from model_library import ModelLibrary
    from model_library_config import SUPABASE_URL,SUPABASE_PUBLISHABLE_KEY
    from PIL import Image
    config=secret_get('model-library')
    if not config.get('token'):raise ValueError('Sign in to the Sakura model library on the owner Companion app before verification.')
    if config.get('refresh_token'):
        response=requests.post(SUPABASE_URL+'/auth/v1/token?grant_type=refresh_token',headers={'apikey':SUPABASE_PUBLISHABLE_KEY},json={'refresh_token':config['refresh_token']},timeout=30)
        if response.status_code!=200:raise ValueError('Owner Sakura library sign-in needs reconnecting.')
        data=response.json();config.update(token=data['access_token'],refresh_token=data['refresh_token'],expires_at=time.time()+data.get('expires_in',3600));secret_set('model-library',config)
    counts={};sample_verified=False
    with tempfile.TemporaryDirectory(prefix='owner-library-check-',dir=root.parent/'private-model-library-pmx') as stage:
        library=ModelLibrary(stage,lambda:config);found={x['id']:x for x in library.catalogue()['models']}
        locations=[('pmx',root.parent/'private-model-library-pmx'),('live2d',root.parent/'private-model-library'),('pmx',root.parent/'private-model-library-account2-pmx'),('live2d',root.parent/'private-model-library-account2')]
        locations.extend((kind,root.parent/('private-model-library'+account+'-'+kind)) for account in ('','-account2') for kind in ('stage','prop'))
        for kind,directory in locations:
            path=directory/'prepared-models.json'
            if not path.is_file():continue
            prepared=json.loads(path.read_text(encoding='utf-8'));counts[kind+'_looks']=counts.get(kind+'_looks',0)+len(prepared)
            for key,value in prepared.items():
                if key not in found or found[key]['sha256']!=value['sha256'] or found[key]['name']!=value['name'] or bool(found[key]['preview'])!=bool(value.get('preview')):raise ValueError('Published catalogue does not match the validated '+kind+' packages or folder names.')
            if not prepared:continue
            sample=min(prepared.values(),key=lambda x:x['bytes'])
            result=library.install(sample['id'])
            if not result.get('models'):raise ValueError('The hosted model did not install.')
            if sample.get('preview'):
                picture=Image.open(io.BytesIO(library.preview(sample['id'])))
                if kind in ('pmx','stage','prop') and picture.n_frames<12:raise ValueError('The published PMX preview does not rotate.')
            sample_verified=True
    return {'pmx_looks':counts.get('pmx_looks',0),'live2d_models':counts.get('live2d_looks',0),'sample_install_verified':sample_verified}

if __name__=='__main__':print(json.dumps(verify()),flush=True)

