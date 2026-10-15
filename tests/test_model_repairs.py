import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app
from model_repairs import read_repairs


class ModelRepairsTests(unittest.TestCase):
    def test_restart_restore_independent_models_and_edited_file_invalidation(self):
        with tempfile.TemporaryDirectory() as folder, patch('app.MODELS_DIR',Path(folder)):
            root=Path(folder);package=root/'pmx'/'あい';package.mkdir(parents=True)
            (package/'one.pmx').write_bytes(b'model-one')
            (package/'two.pmx').write_bytes(b'model-two')
            repairs={'manual':['0|hair'],'diagnostic':{'signature':'[[7,"hair",[0,0,0],[0,0,0,1]]]','frozen':[7],'version':2}}
            first=TestClient(app)
            response=first.post('/api/models/bone-repairs',json={'model':'pmx/あい/one.pmx','repairs':repairs})
            self.assertEqual(response.status_code,200,response.text)
            # A fresh client and file read have no browser profile or previous process cache.
            reopened=TestClient(app).get('/api/models/bone-repairs',params={'model':'pmx/あい/one.pmx'}).json()
            self.assertEqual(reopened['repairs'],repairs)
            self.assertEqual(read_repairs(root,'pmx/あい/one.pmx')['repairs'],repairs)
            self.assertIsNone(read_repairs(root,'pmx/あい/two.pmx')['repairs'])
            self.assertEqual((package/'one.pmx').read_bytes(),b'model-one')
            (package/'one.pmx').write_bytes(b'new-rig-with-more-bones')
            changed=read_repairs(root,'pmx/あい/one.pmx')
            self.assertTrue(changed['invalidated']);self.assertIsNone(changed['repairs'])

    def test_reset_and_reject_invalid_paths_or_overrides(self):
        with tempfile.TemporaryDirectory() as folder, patch('app.MODELS_DIR',Path(folder)):
            root=Path(folder);(root/'one.vrm').write_bytes(b'vrm')
            client=TestClient(app)
            good={'manual':[],'diagnostic':None}
            self.assertEqual(client.post('/api/models/bone-repairs',json={'model':'one.vrm','repairs':good}).status_code,200)
            self.assertEqual(read_repairs(root,'one.vrm')['repairs'],good)
            for model in ['../outside.pmx','missing.pmx','settings.json']:
                self.assertEqual(client.get('/api/models/bone-repairs',params={'model':model}).status_code,400)
            bad={'manual':[],'diagnostic':{'signature':'rig','frozen':[True]}}
            self.assertEqual(client.post('/api/models/bone-repairs',json={'model':'one.vrm','repairs':bad}).status_code,400)


if __name__=='__main__':unittest.main()
