import ctypes,sys
from ctypes import wintypes
pid=int(sys.argv[1]); u=ctypes.WinDLL('user32'); CB=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
@CB
def cb(h,_):
 o=wintypes.DWORD();u.GetWindowThreadProcessId(h,ctypes.byref(o))
 if o.value==pid:
  n=u.GetWindowTextLengthW(h);s=ctypes.create_unicode_buffer(n+1);u.GetWindowTextW(h,s,n+1)
  small=u.SendMessageW(h,0x007F,0,0); big=u.SendMessageW(h,0x007F,1,0)
  print(hex(h),'visible='+str(bool(u.IsWindowVisible(h))),'title='+repr(s.value),'smallIcon='+hex(small or 0),'bigIcon='+hex(big or 0))
 return True
u.EnumWindows(cb,0)
