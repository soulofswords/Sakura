from pathlib import Path
import tempfile
import unittest
from PIL import Image
from fastapi import FastAPI
from fastapi.testclient import TestClient
from local_model_library import router


class LocalModelLibraryTests(unittest.TestCase):
    def test_local_previews_are_guarded_and_cannot_read_outside_model_library(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);character=root/'live2d'/'Annie';character.mkdir(parents=True)
            (character/'model.model3.json').write_text('{"FileReferences":{"Textures":[]}}')
            Image.new('RGB',(32,32),'blue').save(character/'preview.png')
            app=FastAPI();app.include_router(router(root,lambda request:request.headers.get('x-local')=='yes'))
            client=TestClient(app);headers={'x-local':'yes'}
            self.assertEqual(client.get('/api/local-model-library/preview',params={'model':'live2d/Annie/model.model3.json'}).status_code,403)
            response=client.get('/api/local-model-library/preview',params={'model':'live2d/Annie/model.model3.json'},headers=headers)
            self.assertEqual(response.status_code,200);self.assertEqual(response.headers['content-type'],'image/webp')
            for path in ('../secret.model3.json','pmx/test.pmx','live2d/Annie/preview.png'):
                self.assertEqual(client.get('/api/local-model-library/preview',params={'model':path},headers=headers).status_code,404)


    def test_old_cloud_imports_get_names_without_changing_model_paths(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'pmx/import-abcdef/Ringo.pmx';path.parent.mkdir(parents=True);path.write_bytes(b'unchanged model')
            manifest=root/'.library';manifest.mkdir();(manifest/'cloud.json').write_text(json.dumps({'name':'Ananta / Ringo','models':['pmx/import-abcdef/Ringo.pmx']}))
            app=FastAPI();app.include_router(router(root,lambda request:request.headers.get('x-local')=='yes'));client=TestClient(app)
            self.assertEqual(client.get('/api/local-model-library/folder-names').status_code,403)
            data=client.get('/api/local-model-library/folder-names',headers={'x-local':'yes'}).json()
            self.assertEqual(data['names'],{'pmx/import-abcdef':'Ringo'})
            self.assertEqual(path.read_bytes(),b'unchanged model')
