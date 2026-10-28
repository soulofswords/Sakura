import unittest
from app_branding import icon_path,edition_html

class AppBranding(unittest.TestCase):
    def test_shared_html_uses_the_installed_vtuber_identity(self):
        from pathlib import Path
        raw=(Path(__file__).resolve().parents[1]/'static/index.html').read_text(encoding='utf-8')
        branded=edition_html(raw,'vtuber')
        self.assertIn('<title>Sakura VTuber</title>',branded)
        self.assertIn('window.SAKURA_EDITION="vtuber"',branded)
        self.assertIn('<strong>Sakura VTuber</strong>',branded)
        self.assertNotIn('<strong>Sakura Companion</strong>',branded)
        self.assertNotIn('/static/assets/desktop-companion.png',branded)
        self.assertIn('<span class="badge">VTuber</span>',branded)
        companion=edition_html(raw,'companion')
        self.assertIn('<strong>Sakura Companion</strong>',companion)
        self.assertIn('window.SAKURA_EDITION="companion"',companion)

    def test_product_and_mode_identity(self):
        for edition in ('combined','companion'):
            self.assertEqual(icon_path('root',edition,False).name,'companion.ico')
            self.assertEqual(icon_path('root',edition,True).name,'companion-vtuber.ico')
        for tracking in (False,True):
            self.assertEqual(icon_path('root','vtuber',tracking).name,'vtuber.ico')

if __name__=='__main__':unittest.main()
