"""Capture synthetic Sakura frames through DirectShow, without opening a webcam."""
from pathlib import Path
import subprocess
import sys
import threading
import time
import shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from sakura_camera_native import NativeCamera, driver_installed

if not driver_installed():raise RuntimeError('Register Sakura Virtual Camera before this integration check.')
camera=NativeCamera()
stop=threading.Event()
color=np.empty((720,1280,3),dtype=np.uint8);color[:]=[210,45,75]
errors=[]
def produce():
    try:
        while not stop.is_set():camera.send(color);stop.wait(1/30)
    except Exception as error:errors.append(str(error))
thread=threading.Thread(target=produce);thread.start()
output=Path(__file__).resolve().parents[1]/'audit-results'/'sakura-camera-test.rgb';output.parent.mkdir(exist_ok=True)
try:
    result=subprocess.run([shutil.which('ffmpeg'),'-hide_banner','-loglevel','error','-f','dshow','-video_size','1280x720','-framerate','30','-i','video=Sakura Virtual Camera','-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','-y',str(output)],capture_output=True,text=True,timeout=20)
    if result.returncode:raise RuntimeError(result.stderr)
    pixels=np.frombuffer(output.read_bytes(),dtype=np.uint8).reshape(720,1280,3)
    actual=pixels[360,640].astype(int);expected=color[360,640].astype(int)
    if np.max(np.abs(actual-expected))>8:raise AssertionError(f'Capture pixel mismatch: {actual}, expected {expected}')
    if errors:raise RuntimeError(errors)
    print('PASS: Sakura Virtual Camera enumerates and a real DirectShow consumer receives its 1280x720 color-correct frame.')
finally:
    stop.set();thread.join(5);camera.close()
