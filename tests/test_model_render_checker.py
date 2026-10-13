import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('render_checker',Path(__file__).resolve().parents[1]/'tools/check-model-rendering.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)

class ReportTests(unittest.TestCase):
    def test_read_only_server_exposes_texture_check_api(self):
        from fastapi.testclient import TestClient
        server_spec=importlib.util.spec_from_file_location('render_server',Path(__file__).resolve().parents[1]/'tools/model-check-server.py')
        server=importlib.util.module_from_spec(server_spec);server_spec.loader.exec_module(server)
        with TestClient(server.audit) as client:
            response=client.post('/api/models/texture-check',json={'paths':['pmx/__checker_fixture__/missing.png']})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['missing'],['pmx/__checker_fixture__/missing.png'])
    def test_render_failure_is_listed(self):
        report,issues=checker.markdown({'models':[{'path':'pmx/broken.pmx','ok':False,'error':'Invalid geometry'}],'total':1,'complete':True})
        self.assertTrue(issues);self.assertIn('Invalid geometry',report);self.assertIn('Failed: 1',report)
    def test_texture_fallback_is_attention_even_if_render_passes(self):
        report,issues=checker.markdown({'models':[{'path':'pmx/miku.pmx','ok':True,'missingTextures':[{'url':'missing.png'}]}],'complete':True})
        self.assertTrue(issues);self.assertIn('WARN: texture fallback',report)
    def test_live2d_inventory_is_reported_separately_from_3d_audit(self):
        report,issues=checker.markdown({'models':[],'live2d':[{'path':'live2d/model.model3.json'}]})
        self.assertTrue(issues);self.assertIn('Live2D runtime',report);self.assertIn('3D-library audit does not render Live2D',report)
    def test_successful_sample_reports_scope(self):
        report,issues=checker.markdown({'models':[{'path':'vrm/avatar.vrm','ok':True}],'total':1,'libraryTotal':992,'complete':True})
        self.assertFalse(issues);self.assertIn('1 / 1 selected',report);self.assertIn('Full library: 992',report)
    def test_missing_dependency_creates_separate_error_markdown(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(checker.shutil,'which',return_value=None),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(checker.main(['--output',directory]),1)
            root=Path(directory)
            self.assertIn('Node.js is required',(root/'Model-Rendering-Errors.md').read_text())
            self.assertTrue((root/'Model-Rendering-Report.md').is_file())
            self.assertEqual(len(list((root/'model-render-reports').glob('*/Errors.md'))),1)

if __name__=='__main__':unittest.main()
