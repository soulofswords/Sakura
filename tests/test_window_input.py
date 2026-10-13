import unittest
from window_input import set_click_through, set_topmost
class FakeUser:
 def __init__(self): self.style=0x80008;self.position=None
 def GetWindowLongPtrW(self,*args): return self.style
 def SetWindowLongPtrW(self,hwnd,index,style): self.style=style
 def SetWindowPos(self,*args): self.position=args
class InputTests(unittest.TestCase):
 def test_z_order_preserves_layered_surface_without_frame_change(self):
  class ZOrderUser(FakeUser):
   def SetWindowPos(self,*args):
    self.position=args
    self.style=(self.style|8) if args[1]==-1 else (self.style&~8)
    return True
  user=ZOrderUser();original=user.style
  self.assertTrue(set_topmost(1,True,user));self.assertIsNone(user.position)
  self.assertTrue(set_topmost(1,False,user));self.assertEqual(user.style,original&~8)
  self.assertEqual(user.position[-1],0x13)
  self.assertTrue(set_topmost(1,True,user));self.assertEqual(user.style,original)
  self.assertEqual(user.position[1],-1)
 def test_failed_z_order_change_is_reported(self):
  user=FakeUser()
  self.assertFalse(set_topmost(1,False,user))
 def test_unchanged_input_mode_does_not_refresh_native_frame(self):
  user=FakeUser()
  self.assertTrue(set_click_through(1,False,user))
  self.assertIsNone(user.position)
  self.assertTrue(set_click_through(1,True,user))
  user.position=None
  self.assertTrue(set_click_through(1,True,user))
  self.assertIsNone(user.position)
 def test_click_through_and_restore_preserve_renderer_and_topmost(self):
  user=FakeUser(); original=user.style
  self.assertTrue(set_click_through(1,True,user));self.assertEqual(user.style,original|0x20)
  self.assertTrue(set_click_through(1,False,user));self.assertEqual(user.style,original)
  self.assertTrue(user.position[-1]&0x10)
