"""Optional Windows Spout sender. All native calls live on one worker thread."""
import queue
import secrets
import sys
import threading
import time

class SpoutOutput:
    def __init__(self):
        self.lock=threading.RLock();self.frames=queue.Queue(maxsize=1)
        self.worker=None;self.stop_event=threading.Event();self.ready=threading.Event()
        self.enabled=False;self.error='';self.name='Sakura';self.token='';self.sent=0;self.last_frame=0
    def status(self):
        return {'supported':sys.platform=='win32','enabled':self.enabled,'error':self.error,
                'name':self.name,'frames':self.sent}
    def configure(self,enabled,name='Sakura'):
        with self.lock:
            self.stop()
            if not enabled:return {**self.status(),'token':''}
            if sys.platform!='win32':raise ValueError('Spout2 output is available on Windows only.')
            if not isinstance(name,str) or not name.strip() or len(name)>64 or any(ord(c)<32 for c in name):raise ValueError('Enter a sender name between 1 and 64 characters.')
            self.name=name.strip();self.error='';self.sent=0;self.token=secrets.token_urlsafe(24)
            self.stop_event=threading.Event();self.ready=threading.Event();self.last_frame=time.monotonic()
            self.worker=threading.Thread(target=self._run,daemon=True,name='sakura-spout');self.worker.start()
            if not self.ready.wait(5):self.stop();raise ValueError('Spout initialization timed out.')
            if self.error:raise ValueError(self.error)
            return {**self.status(),'token':self.token}
    def _run(self):
        sender=None
        try:
            import SpoutGL
            sender=SpoutGL.SpoutSender();sender.setSenderName(self.name)
            self.enabled=True;self.ready.set()
            while not self.stop_event.is_set():
                try:pixels,width,height=self.frames.get(timeout=.5)
                except queue.Empty:
                    if time.monotonic()-self.last_frame>15:break
                    continue
                if not sender.sendImage(pixels,width,height,0x1908,False,0):raise RuntimeError('Spout could not send the frame. Check GPU/receiver compatibility.')
                sender.setFrameSync(self.name);self.sent+=1
        except Exception as error:self.error='Spout output failed: '+str(error)
        finally:
            if sender:sender.releaseSender()
            self.enabled=False;self.ready.set()
    def submit(self,token,pixels,width,height):
        with self.lock:
            if not self.enabled or not secrets.compare_digest(token,self.token):raise ValueError('Spout session is inactive. Enable output again.')
            if not 1<=width<=1280 or not 1<=height<=1280 or len(pixels)!=width*height*4:raise ValueError('Invalid RGBA frame dimensions.')
            self.last_frame=time.monotonic()
            try:self.frames.get_nowait()
            except queue.Empty:pass
            self.frames.put_nowait((pixels,width,height))
    def stop(self):
        self.stop_event.set()
        if self.worker and self.worker.is_alive():
            self.worker.join(5)
            if self.worker.is_alive():raise ValueError('Spout is still stopping. Try again shortly.')
        self.worker=None;self.enabled=False;self.token=''
        while not self.frames.empty():
            try:self.frames.get_nowait()
            except queue.Empty:break

output=SpoutOutput()
