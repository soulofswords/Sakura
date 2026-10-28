import importlib.util
from pathlib import Path
import re
import unittest

BASE=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,BASE/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

class ReleasePayloadTests(unittest.TestCase):
    def test_source_backups_and_debug_maps_are_excluded_at_both_packaging_layers(self):
        builder=load('asset_filter_builder','tools/build-installers.py')
        protection=load('asset_filter_protection','tools/release-protection.py')
        for name in ('app.js.bak','app.js.before-tracking60.bak','style.css.backup','code.js.map','code.js.orig','code.js~'):
            with self.subTest(name=name):
                self.assertFalse(builder.release_asset_allowed(name))
                self.assertFalse(protection.protected_asset_allowed(name))
        for name in ('app.js','style.css','model-viewer.js','face_landmarker.task','LICENSE'):
            self.assertTrue(builder.release_asset_allowed(name))
            self.assertTrue(protection.protected_asset_allowed(name))

    def test_no_existing_static_backups_are_selected_for_a_new_release(self):
        builder=load('existing_asset_filter','tools/build-installers.py')
        selected=[p for p in (BASE/'static').rglob('*') if p.is_file() and builder.release_asset_allowed(p)]
        self.assertTrue(any(p.name=='model-viewer.js' for p in selected))
        self.assertFalse(any('.bak' in p.name for p in selected))

    def test_pages_loaded_by_shipped_scripts_are_packaged(self):
        builder=load('packaged_pages_builder','tools/build-installers.py')
        packaged={name for _,name in builder.app_files()}
        referenced={'Sakura'+match
                    for script in (BASE/'static/js').glob('*.js')
                    for match in re.findall(r'/static/[\w./-]+\.html',script.read_text(encoding='utf-8'))}
        self.assertIn('Sakura/static/model-library-preview.html',referenced)
        self.assertEqual(sorted(referenced-packaged),[])
