import importlib.util
from pathlib import Path
import re
import unittest
from unittest.mock import patch

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
        # This checks page inclusion in a clean checkout, where optional speech
        # weights are absent. Actual installer builds still verify every asset.
        with patch.dict('kokoro_speech.ASSETS',{},clear=True):
            packaged={name for _,name in builder.app_files()}
        referenced={'Sakura'+match
                    for script in (BASE/'static/js').glob('*.js')
                    for match in re.findall(r'/static/[\w./-]+\.html',script.read_text(encoding='utf-8'))}
        self.assertIn('Sakura/static/model-library-preview.html',referenced)
        self.assertEqual(sorted(referenced-packaged),[])

    def test_real_packaging_rejects_missing_voice_assets(self):
        builder=load('missing_voice_builder','tools/build-installers.py')
        with patch.dict('kokoro_speech.ASSETS',{'missing-ci-test.bin':(1,'invalid')},clear=True):
            with self.assertRaisesRegex(RuntimeError,'Kokoro speech assets'):
                list(builder.app_files())


    def test_editor_payload_excludes_reference_jobs_and_keeps_distribution(self):
        import tempfile
        builder=load('editor_asset_filter','tools/build-installers.py')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            allowed=['PmxEditor.exe','Lib/PEPlugin/PEPlugin.dll','_plugin/User/OtherPlugin.dll','README.txt']
            blocked=['_plugin/User/SakuraAppearanceReference.dll',
                     '_plugin/User/SakuraAppearanceReference.dll.lock',
                     '_plugin/User/SakuraAppearanceReference.dll.owner.json',
                     '_plugin/User/sakuraappearancereference.tmp',
                     'settings.lock','example.pmx','example.pmd','editor.log','test.bak']
            for name in allowed+blocked:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'test')
            packaged={name for _,name in builder.editor_files(root)}
            self.assertEqual(packaged,{'Sakura/tools/pmx-editor/'+name for name in allowed})

    def test_both_edition_installers_default_to_local_app_data(self):
        import tempfile
        split=load('install_default_editions','tools/build-split-installers.py')
        for edition,display in [('companion','Sakura Companion'),('vtuber','Sakura VTuber')]:
            with self.subTest(edition=edition),tempfile.TemporaryDirectory() as folder:
                split.edition_sources(edition,Path(folder))
                source=(Path(folder)/'Installer.cs').read_text(encoding='utf-8')
                self.assertIn('string defaultPath=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"'+display+'")',source)
                self.assertIn('Text=existing??defaultPath',source)
