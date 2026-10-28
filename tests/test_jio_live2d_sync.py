import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
from urllib.parse import urlparse,parse_qs

from PIL import Image
import pytest

ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT/'tools'))
spec=importlib.util.spec_from_file_location('jio_live2d_sync',ROOT/'tools/sync-jio-live2d-sources.py')
sync=importlib.util.module_from_spec(spec);spec.loader.exec_module(sync)


@pytest.mark.parametrize('portrait',[True,False])
def test_new_jio_folder_gets_validated_package_and_optional_portrait(tmp_path,monkeypatch,portrait):
    app=tmp_path/'Sakura';(app/'tools').mkdir(parents=True)
    shutil.copyfile(ROOT/'tools/publish-model-library.py',app/'tools/publish-model-library.py')
    picture=io.BytesIO();Image.new('RGBA',(8,8),'pink').save(picture,format='PNG')
    content={'descriptor':json.dumps({'Version':3,'FileReferences':{'Moc':'hero.moc3','Textures':['tex/texture.png']}}).encode(),
             'moc':b'MOC3test','texture':picture.getvalue(),'portrait':picture.getvalue()}
    def file(key,name):return {'objectKey':key,'objectName':name,'objectType':'FL','sizeInBytes':len(content[key]),'hash':hashlib.md5(content[key]).hexdigest()}
    folders={'root':[{'objectKey':'live','objectName':'Live2d','objectType':'FR'}],
             'live':[{'objectKey':'hero','objectName':'Hero','objectType':'FR'},
                     {'objectKey':'generated','objectName':'existing-package.zip','objectType':'FL'}],
             'hero':[file('descriptor','hero.model3.json'),file('moc','hero.moc3'),{'objectKey':'tex','objectName':'tex','objectType':'FR'}],
             'tex':[file('texture','texture.png')]}
    if portrait:folders['hero'].append(file('portrait','portrait.png'))
    def request(method,url,**kwargs):
        assert method=='GET','Source browsing must never write to Jio.'
        key=parse_qs(urlparse(url).query)['folderKey'][0]
        return {'objects':folders[key]}
    owner=SimpleNamespace(resume=lambda:None,session={'rootFolderKey':'root','dcGroupCode':'JAWS','authToken':{'accessToken':'test'},'userId':'owner','deviceKey':'device'},headers={},request=request)
    monkeypatch.setattr(sync,'JioConnection',lambda:owner)
    class Response:
        status_code=200
        def __init__(self,data):self.data=data
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def iter_content(self,size):yield self.data
    class Session:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url,**kwargs):
            assert kwargs['allow_redirects'] is False
            return Response(content[url.rsplit('/',1)[-1]])
    monkeypatch.setattr(sync.requests,'Session',Session)
    assert sync.main(app)==0
    out=tmp_path/'private-model-library'
    entries=json.loads((out/'prepared-models.json').read_text());assert len(entries)==1
    entry=next(iter(entries.values()))
    assert entry['name']=='Hero' and entry['preview'] is portrait
    assert (out/(entry['id']+'.zip')).is_file()
    assert (out/(entry['id']+'.webp')).exists() is portrait
    # An unchanged second pass does not download or rebuild the model.
    before=(out/(entry['id']+'.zip')).stat().st_mtime_ns
    assert sync.main(app)==0
    assert (out/(entry['id']+'.zip')).stat().st_mtime_ns==before
