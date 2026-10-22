import unittest
from app_branding import icon_path

class AppBranding(unittest.TestCase):
    def test_product_and_mode_identity(self):
        for edition in ('combined','companion'):
            self.assertEqual(icon_path('root',edition,False).name,'companion.ico')
            self.assertEqual(icon_path('root',edition,True).name,'companion-vtuber.ico')
        for tracking in (False,True):
            self.assertEqual(icon_path('root','vtuber',tracking).name,'vtuber.ico')

if __name__=='__main__':unittest.main()
