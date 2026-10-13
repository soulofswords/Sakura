import unittest
from companion_hotkey import parse_hotkey
class ShortcutTests(unittest.TestCase):
    def test_default_and_normalization(self):
        self.assertEqual(parse_hotkey('')[0],'Ctrl+Shift+T')
        self.assertEqual(parse_hotkey('Shift+Ctrl+y')[:3],('Ctrl+Shift+Y',6,ord('Y')))
        self.assertEqual(parse_hotkey('Alt+F8')[2],0x77)
        self.assertEqual(parse_hotkey('Meta+Shift+K')[3],'<shift>+<cmd>+k')
    def test_unsafe_and_reserved_shortcuts_rejected(self):
        for value in ['T','Shift+T','Ctrl+Shift+H','Ctrl+Ctrl+T','Ctrl+F13','Ctrl+Space','Ctrl+😄']:
            with self.assertRaises(ValueError): parse_hotkey(value)
if __name__=='__main__':unittest.main()
