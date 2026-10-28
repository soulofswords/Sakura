from unittest.mock import patch
import pytest
from model_import import import_package
from scenery_assets import local_assets,asset_kind
from tests.test_model_import import pmx_with_bones


def test_nonhumanoid_scenery_import_is_separate_from_characters(tmp_path):
    files=[('Garden/Garden.pmx',pmx_with_bones([])),('Garden/textures/floor.png',b'texture')]
    with pytest.raises(ValueError):import_package(tmp_path,files,'pmx')
    result=import_package(tmp_path,files,'pmx',asset_kind='stage')
    assert result['models'][0].startswith('pmx/Stages/')
    rows=local_assets(tmp_path,'stage');assert rows[0]['path']==result['models'][0]
    assert not local_assets(tmp_path,'prop')
    again=import_package(tmp_path,files,'pmx',asset_kind='stage')
    assert again['already_installed']
    prop=import_package(tmp_path,files,'pmx',asset_kind='prop')
    assert prop['models'][0].startswith('pmx/Tools & Props/')


def test_scenery_routes_guard_import_and_nested_listing(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from scenery_assets import router
    app=FastAPI();app.include_router(router(tmp_path,lambda request:request.headers.get('x-local')=='yes'))
    client=TestClient(app)
    assert client.get('/api/scenery/assets').status_code==403
    body=[('files',('City/Apartment/apartment.pmx',pmx_with_bones([]),'application/octet-stream'))]
    assert client.post('/api/scenery/import',data={'kind':'stage'},files=body).status_code==403
    response=client.post('/api/scenery/import',data={'kind':'stage'},files=body,headers={'x-local':'yes'})
    assert response.status_code==200,response.text
    rows=client.get('/api/scenery/assets?kind=stage',headers={'x-local':'yes'}).json()['models']
    assert rows[0]['asset_kind']=='stage' and rows[0]['folders']
    assert client.get('/api/scenery/assets?kind=../',headers={'x-local':'yes'}).status_code==400


def test_character_list_hides_dedicated_stage_and_tools(tmp_path):
    import app
    from local_client import TestClient
    for kind in ('stage','prop'):import_package(tmp_path,[('prop.pmx',pmx_with_bones([]))],'pmx',asset_kind=kind)
    with patch.object(app,'MODELS_DIR',tmp_path):assert not TestClient(app.app).get('/api/models').json()['models']


def test_cloud_asset_names_are_explicit_namespaces():
    assert asset_kind('Stages / City / apartment')=='stage'
    assert asset_kind('Tools & Props / Weapons / Sword')=='prop'
    assert asset_kind('Miku universe / Haku')=='character'


def test_reusing_bytes_does_not_merge_character_and_scenery_libraries(tmp_path):
    data=pmx_with_bones(['全ての親','センター','上半身','頭','左腕','右腕','左足','右足'])
    stage=import_package(tmp_path,[('model.pmx',data)],'pmx',asset_kind='stage')
    character=import_package(tmp_path,[('model.pmx',data)],'pmx')
    assert stage['models']!=character['models']
    assert not character.get('already_installed')


def test_scenery_cloud_package_installs_in_its_own_library(tmp_path):
    import hashlib,io,zipfile
    from model_library import ModelLibrary
    blob=io.BytesIO()
    with zipfile.ZipFile(blob,'w') as archive:archive.writestr('City/stage.pmx',pmx_with_bones([]))
    data=blob.getvalue();entry={'id':'city','name':'Stages / City / stage','format':'pmx','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    library=ModelLibrary(tmp_path,lambda:{})
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def iter_content(self,size):yield data
    with patch.object(library,'catalogue',return_value={'models':[entry]}),patch.object(library,'_request',return_value=Response()):
        result=library.install('city')
    assert all(path.startswith('pmx/Stages/') for path in result['models'])
