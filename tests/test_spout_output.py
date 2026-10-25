import time,unittest,sys,array
from spout_output import SpoutOutput
@unittest.skipUnless(sys.platform=='win32','Spout2 is Windows only')
class SpoutTests(unittest.TestCase):
 def test_native_sender_enable_frame_validation_and_stop(self):
  sender=SpoutOutput()
  try:
   result=sender.configure(True,'Sakura-Background-Test')
   self.assertTrue(result['enabled'])
   with self.assertRaises(ValueError):sender.submit('wrong',bytes(64*64*4),64,64)
   with self.assertRaises(ValueError):sender.submit(result['token'],b'invalid',64,64)
   sender.submit(result['token'],bytes([200,30,50,128])*64*64,64,64)
   deadline=time.monotonic()+3
   while not sender.sent and time.monotonic()<deadline:time.sleep(.02)
   self.assertEqual(sender.sent,1,sender.error)
   import SpoutGL
   receiver=SpoutGL.SpoutReceiver()
   self.assertIn('Sakura-Background-Test',receiver.getSenderList())
   receiver.releaseReceiver()
   receiver=SpoutGL.SpoutReceiver();receiver.setReceiverName('Sakura-Background-Test');buf=None
   try:
    for _ in range(40):
     sender.submit(result['token'],bytes([200,30,50,128])*64*64,64,64);time.sleep(.03)
     receiver.receiveImage(buf,0x1908,False,0)
     if receiver.isUpdated():buf=array.array('B',[0]*(receiver.getSenderWidth()*receiver.getSenderHeight()*4))
     if buf and buf[3]==128:break
    self.assertIsNotNone(buf);self.assertEqual(list(buf[:4]),[200,30,50,128])
   finally:receiver.releaseReceiver()
  finally:sender.stop()
  self.assertFalse(sender.enabled);self.assertFalse(sender.worker)
 def test_full_hd_frames_are_not_limited_to_preview_resolution(self):
  sender=SpoutOutput();sender.enabled=True;sender.token='test'
  pixels=bytes(1920*1080*4)
  sender.submit('test',pixels,1920,1080)
  queued=sender.frames.get_nowait()
  self.assertEqual(queued[1:],(1920,1080))
  with self.assertRaises(ValueError):sender.submit('test',b'',2561,1440)
 def test_disabled_does_not_start_worker(self):
  sender=SpoutOutput();self.assertFalse(sender.configure(False)['enabled']);self.assertIsNone(sender.worker)
if __name__=='__main__':unittest.main()
