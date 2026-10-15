import ctypes
import types
import unittest
from unittest.mock import patch
import native_clipboard

class Function:
    def __init__(self,call):self.call=call
    def __call__(self,*args):return self.call(*args)

class NativeClipboardTests(unittest.TestCase):
    def test_unicode_transfer_and_ownership_cleanup(self):
        buffer=ctypes.create_string_buffer(8192);events=[]
        user=types.SimpleNamespace(
            CreateWindowExW=Function(lambda *args:123),DestroyWindow=Function(lambda owner:events.append(('destroy',owner))),
            OpenClipboard=Function(lambda owner:events.append(('open',owner)) or 1),
            EmptyClipboard=Function(lambda:1),SetClipboardData=Function(lambda kind,handle:events.append(('set',kind,handle)) or handle),
            CloseClipboard=Function(lambda:events.append(('close',))))
        kernel=types.SimpleNamespace(GlobalAlloc=Function(lambda *args:42),GlobalLock=Function(lambda handle:ctypes.addressof(buffer)),
            GlobalUnlock=Function(lambda handle:1),GlobalFree=Function(lambda handle:events.append(('free',handle))))
        with patch('native_clipboard.ctypes.WinDLL',side_effect=lambda name,**kwargs:user if name=='user32' else kernel):
            self.assertTrue(native_clipboard.copy_text('http://192.168.1.20:8771 🌸')['copied'])
        self.assertIn(('open',123),events);self.assertIn(('set',13,42),events)
        self.assertIn(('close',),events);self.assertIn(('destroy',123),events)
        self.assertNotIn(('free',42),events,'Windows owns memory after successful transfer')
        self.assertEqual(buffer.raw[:len(('http://192.168.1.20:8771 🌸\0').encode('utf-16-le'))].decode('utf-16-le'),'http://192.168.1.20:8771 🌸\0')

    def test_invalid_clipboard_inputs(self):
        for value in (None,'bad\0text','x'*4097):
            with self.assertRaises(ValueError):native_clipboard.copy_text(value)
