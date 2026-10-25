"""Synthetic LAN-server capacity check; does not measure phone camera inference."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hashlib,json,socket,tempfile,threading,time,statistics
import httpx,uvicorn
from mobile_link import MobileLink
import ctypes
# A foreground Chromium render loop uses high-resolution timers. Match that
# timing in this console-only benchmark and restore it when the check exits.
if sys.platform=='win32':ctypes.windll.winmm.timeBeginPeriod(1)

with tempfile.TemporaryDirectory() as temp:
 link=MobileLink(Path(temp)/'devices.json');link.enabled=True;link.tokens.add('synthetic-test-token')
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 server=uvicorn.Server(uvicorn.Config(link.api,log_level='error',access_log=False));thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
 deadline=time.perf_counter()+5
 while not server.started:
  if time.perf_counter()>deadline:raise RuntimeError('Test server did not start')
  time.sleep(.01)
 point={'x':.123456,'y':.654321,'z':-.012345,'visibility':.99}
 sample={'face':{'landmarks':[point]*478,'matrix':[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1], 'blendshapes':[{'categoryName':'jawOpen','score':.2}]},'hands':[{'side':side,'confidence':.99,'landmarks':[point]*21,'world':[point]*21} for side in ['Left','Right']], 'pose':{'landmarks':[point]*33,'world':[point]*33},'trackingMetrics':{'cameraFps':60,'processedFps':60}}
 delays=[];received=[];done=threading.Event()
 def consume():
  while not done.is_set():
   frame=link.poll({})['frame']
   if frame:received.append(frame['trackingMetrics']['sequence'])
   done.wait(.004)
 consumer=threading.Thread(target=consume);consumer.start()
 try:
  with httpx.Client(base_url=f'http://127.0.0.1:{port}',headers={'Authorization':'Bearer synthetic-test-token'},timeout=2) as client:
   began=time.perf_counter()
   for sequence in range(180):
    wait=began+sequence/60-time.perf_counter()
    if wait>0:time.sleep(wait)
    sample['trackingMetrics']['sequence']=sequence;start=time.perf_counter();response=client.post('/frame',json=sample);response.raise_for_status();delays.append((time.perf_counter()-start)*1000)
   elapsed=time.perf_counter()-began;time.sleep(.05)
  print(json.dumps({'synthetic_uploads':180,'elapsed_seconds':round(elapsed,3),'upload_fps':round(180/elapsed,1),'distinct_pc_samples':len(received),'median_http_ms':round(statistics.median(delays),2),'payload_bytes':len(json.dumps(sample)),'scope':'localhost server and latest-frame consumer only; not real-phone camera/GPU/Wi-Fi'},indent=2))
  if 180/elapsed<55 or len(set(received))<170:raise AssertionError('Server did not sustain the synthetic 60 FPS workload')
 finally:
  done.set();consumer.join();server.should_exit=True;thread.join(5);sock.close();link.stop()
  if sys.platform=='win32':ctypes.windll.winmm.timeEndPeriod(1)
