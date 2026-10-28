"""A refreshed app must carry reset handlers as well as the library panel."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


class LibrarySyncTests(unittest.TestCase):
    def test_sync_attaches_both_routers_and_preserves_other_edits_on_repeat(self):
        source=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('library_sync',source/'tools/sync-model-library.py')
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'static').mkdir()
            (root/'app.py').write_text('CUSTOM = "preserve"\ndef _started_locally(request): pass\ndef _served_locally(request): pass\nif __name__ == "__main__":\n    pass\n')
            (root/'static/index.html').write_text('<script src="/static/js/app.js?v=other-work"></script></body>')
            module.sync(root)
            first=(root/'app.py').read_text()
            module.sync(root)
            self.assertEqual(first,(root/'app.py').read_text())
            self.assertIn('CUSTOM = "preserve"',first)
            self.assertEqual(first.count('app.include_router(model_library_confirm_router('),1)
            self.assertEqual((root/'model_library_confirm.py').read_bytes(),(source/'model_library_confirm.py').read_bytes())
            markup=(root/'static/index.html').read_text()
            self.assertIn('app.js?v=other-work',markup)
            self.assertEqual(markup.count('/static/js/model-library.js'),1)
