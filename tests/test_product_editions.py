import asyncio
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import app

class ProductEditionTests(unittest.IsolatedAsyncioTestCase):
    async def test_modes_are_locked_to_the_product(self):
        for edition,requested in [('vtuber',False)]:
            with patch.object(app,'EDITION',edition):
                result=await app.set_tracking_mode({'enabled':requested})
                self.assertEqual(result.status_code,409)
    async def test_vtuber_cannot_call_chat_or_local_download(self):
        import httpx
        with patch.object(app,'EDITION','vtuber'):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app),base_url='http://test') as client:
                for path in ['/api/chat','/api/local-model/install','/api/ollama/models','/api/vtuber/reply']:
                    result=await client.post(path,json={})
                    self.assertEqual(result.status_code,409)
                    self.assertNotIn('AI',result.text)
    async def test_preference_cannot_change_product_edition(self):
        with patch.object(app,'EDITION','vtuber'):
            self.assertTrue(app.get_settings()['vtuber_tracking_only'])
        with patch.object(app,'EDITION','companion'):
            self.assertEqual(app.get_settings()['product_edition'],'companion')

class ProductTemplateTests(unittest.TestCase):
    def test_release_templates(self):
        spec=importlib.util.spec_from_file_location('split_builder',Path('tools/build-split-installers.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as root:
            for edition in ['vtuber','companion']:
                stage=Path(root)/edition;stage.mkdir();display,launcher=module.edition_sources(edition,stage)
                self.assertIn(display,(stage/'Installer.cs').read_text(encoding='utf-8'))
                self.assertIn(launcher,(stage/'Installer.cs').read_text(encoding='utf-8'))
                source=(stage/'Launcher.cs').read_text(encoding='utf-8')
                html=(stage/'index.html').read_text(encoding='utf-8')
                opened=html.index('id="startup-render-status"')
                startup=html[opened:html.index('</div>',opened)]
                if edition=='vtuber':
                    self.assertNotIn('desktop-companion.png',html)
                    self.assertNotIn('companion-vtuber.png',html)
                    self.assertIn('vtuber-app.png',startup)
                    self.assertIn('<strong>Sakura VTuber</strong>',startup)
                else:
                    self.assertIn('startup-logo-flower" src="/static/assets/desktop-companion.png',startup)
                    self.assertIn('startup-logo-vtuber" src="/static/assets/companion-vtuber.png',startup)
                    self.assertNotIn('vtuber-app.png',html)
                    self.assertIn('<strong>Sakura Companion</strong>',startup)
                    self.assertIn('html.vtuber-startup #startup-render-status .startup-logo-flower { display: none; }',html)
                    self.assertIn('html.vtuber-startup #startup-render-status .startup-logo-vtuber { display: block; }',html)
                if edition=='vtuber':
                    self.assertNotIn('LocalModelDialog',source)
                    self.assertNotIn('new StartupDialog',source)
                    self.assertNotIn('Gemini',(stage/'Installer.cs').read_text(encoding='utf-8'))
                else:self.assertIn('"gemini","local","vtuber"',(stage/'StartupDialog.cs').read_text(encoding='utf-8'))
