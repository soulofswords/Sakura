"""Opt-in LAN relay: exposes only paired phone controls, never the PC API."""
import asyncio
import ipaddress
import secrets
import socket
import threading
import time
import hashlib
import json
import re
from pathlib import Path
from collections import deque
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

class MobileLink:
    def __init__(self,store_path=None):
        self.enabled=False;self.code='';self.tokens=set();self.commands=deque(maxlen=50)
        from product import EDITION
        from config import BASE_DIR
        self.store=Path(store_path) if store_path else BASE_DIR/'phone-devices.json'
        try:self.devices=json.loads(self.store.read_text(encoding='utf-8'))
        except (OSError,ValueError):self.devices={}
        if not isinstance(self.devices,dict):self.devices={}
        self.devices={key:value for key,value in self.devices.items() if isinstance(key,str) and isinstance(value,dict)
            and re.fullmatch(r'[0-9a-f]{64}',str(value.get('token_hash','')))}
        self.edition=EDITION;self.frame=None;self.camera=None;self.state={'edition':EDITION};self.lock=threading.RLock();self.server=None;self.attempts={}
        self.pc_port=8766;self.port=8772 if EDITION=='vtuber' else 8771;self.code_expires=0;self.thread=None
        self.api=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
        self.api.add_api_route('/pair',self.pair,methods=['POST'])
        self.api.add_api_route('/state',self.phone_state,methods=['GET'])
        self.api.add_api_route('/command',self.command,methods=['POST'])
        self.api.add_api_route('/frame',self.tracking_frame,methods=['POST'])
        self.api.add_api_route('/camera',self.camera_frame,methods=['POST'])
        self.api.add_api_route('/chat',self.chat,methods=['POST'])
        self.api.add_api_route('/gemini',self.gemini,methods=['POST'])
        self.api.middleware('http')(self.guard)

    async def guard(self,request,call_next):
        host=request.client.host if request.client else ''
        try:private=ipaddress.ip_address(host).is_private
        except ValueError:private=False
        if not self.enabled or not private:return JSONResponse({'error':'Phone link is off.'},403)
        if int(request.headers.get('content-length','0') or 0)>250000:return JSONResponse({'error':'Request too large'},413)
        if request.url.path!='/pair':
            token=request.headers.get('authorization','').removeprefix('Bearer ')
            digest=hashlib.sha256(token.encode()).hexdigest()
            with self.lock:device=next((d for d in self.devices.values() if secrets.compare_digest(str(d.get('token_hash','')),digest)),None)
            if not token or (token not in self.tokens and device is None):return JSONResponse({'error':'Pair with the PC first.'},401)
            if device is not None:device['last_seen']=time.time()
        return await call_next(request)

    def start(self,pc_port):
        self.pc_port=pc_port
        if not self.enabled:
            self.enabled=True;self.code=f'{secrets.randbelow(1000000):06d}';self.code_expires=time.time()+300
            self.server=uvicorn.Server(uvicorn.Config(self.api,host='0.0.0.0',port=self.port,log_level='warning',access_log=False))
            if self.thread and self.thread.is_alive():self.thread.join(timeout=2)
            self.thread=threading.Thread(target=self.server.run,daemon=True);self.thread.start()
        return self.info()

    def info(self):
        addresses=set()
        try:
            for entry in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET):
                address=entry[4][0]
                if ipaddress.ip_address(address).is_private and not address.startswith('127.'):addresses.add(address)
        except OSError:pass
        with self.lock:devices=[{'id':id,'name':device.get('name','Android device'),'connected':self.enabled and time.time()-device.get('last_seen',0)<15} for id,device in self.devices.items()]
        return {'enabled':self.enabled,'code':self.code if self.enabled else '',
                'addresses':[f'http://{ip}:{self.port}' for ip in sorted(addresses)],'port':self.port,'paired':len(self.tokens),
                'devices':devices}

    def save_devices(self):
        with self.lock:
            self.store.parent.mkdir(parents=True,exist_ok=True)
            pending=self.store.with_suffix('.tmp');pending.write_text(json.dumps(self.devices,indent=2),encoding='utf-8');pending.replace(self.store)

    def forget_device(self,device_id):
        with self.lock:self.devices.pop(device_id,None);self.tokens.clear();self.save_devices()
        return self.info()

    def new_pairing_code(self):
        if not self.enabled:raise ValueError('Enable phone connection first.')
        self.code=f'{secrets.randbelow(1000000):06d}';self.code_expires=time.time()+300
        return self.info()

    def stop(self):
        self.enabled=False;self.tokens.clear();self.code='';self.frame=None;self.camera=None;self.commands.clear()
        if self.server:self.server.should_exit=True

    async def pair(self,request:Request):
        host=request.client.host;now=time.time()
        attempts=[stamp for stamp in self.attempts.get(host,[]) if now-stamp<60]
        if len(attempts)>=5:return JSONResponse({'error':'Too many attempts. Wait one minute.'},429)
        attempts.append(now);self.attempts[host]=attempts
        body=await request.json()
        if now>self.code_expires or not secrets.compare_digest(str(body.get('code','')),self.code):
            return JSONResponse({'error':'Pairing code is wrong or expired. Turn phone link off and on.'},401)
        token=secrets.token_urlsafe(32);self.tokens.add(token)
        device_id=str(body.get('device_id') or secrets.token_hex(16))[:64]
        if not re.fullmatch(r'[A-Za-z0-9_-]+',device_id):return JSONResponse({'error':'Invalid device identifier'},400)
        if device_id not in self.devices and len(self.devices)>=32:return JSONResponse({'error':'Forget an old device before adding another.'},409)
        with self.lock:
            self.devices[device_id]={'name':str(body.get('device_name') or 'Android device')[:80],
                'token_hash':hashlib.sha256(token.encode()).hexdigest(),'last_seen':now}
            self.save_devices()
        return {'token':token,'name':'Sakura','edition':self.state.get('edition','companion')}

    async def phone_state(self):
        return self.state

    async def command(self,request:Request):
        body=await request.json();kind=body.get('type')
        if kind not in ('expression','clear-expressions','tracking-start','tracking-stop','camera-start','camera-stop','calibrate'):
            return JSONResponse({'error':'Unsupported control'},400)
        if kind.startswith('camera-') and (self.edition=='vtuber' or self.state.get('edition')=='vtuber'):
            return JSONResponse({'error':'Companion camera viewing needs Sakura Companion.'},409)
        if kind=='expression' and body.get('name') not in self.state.get('expressions',[]):
            return JSONResponse({'error':'Expression is not available on the current model.'},400)
        body={key:value for key,value in body.items() if key in ('type','name','enabled')}
        with self.lock:self.commands.append(body)
        return {'ok':True}

    async def camera_frame(self,request:Request):
        if self.edition=='vtuber' or self.state.get('edition')=='vtuber':
            return JSONResponse({'error':'Companion camera viewing needs Sakura Companion.'},409)
        import base64,binascii
        body=await request.json();image=body.get('image')
        try:
            if not isinstance(image,str) or not 4<=len(image)<=220000:raise ValueError()
            if not base64.b64decode(image,validate=True).startswith(b'\xff\xd8\xff'):raise ValueError()
        except (ValueError,binascii.Error):return JSONResponse({'error':'Invalid bounded JPEG camera frame.'},400)
        with self.lock:self.camera={'image':image,'timestamp':time.time()}
        return {'ok':True}

    async def tracking_frame(self,request:Request):
        data=await request.json();face=data.get('face',{})
        matrix=face.get('matrix')
        import math
        if not isinstance(matrix,list) or len(matrix)!=16 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in matrix):
            return JSONResponse({'error':'Invalid face pose'},400)
        landmarks=face.get('landmarks',[]);blendshapes=face.get('blendshapes',[])
        if not isinstance(landmarks,list) or len(landmarks)>500 or not isinstance(blendshapes,list) or len(blendshapes)>100:
            return JSONResponse({'error':'Invalid face signals'},400)
        if any(not isinstance(p,dict) or any(not isinstance(p.get(k),(int,float)) or not math.isfinite(p[k]) for k in ('x','y','z')) for p in landmarks):
            return JSONResponse({'error':'Invalid face landmarks'},400)
        if any(not isinstance(p,dict) or not isinstance(p.get('categoryName'),str) or not isinstance(p.get('score'),(int,float)) or not math.isfinite(p['score']) for p in blendshapes):
            return JSONResponse({'error':'Invalid face blendshapes'},400)
        clean={'matrix':matrix,'landmarks':landmarks,'blendshapes':blendshapes}
        with self.lock:self.frame={'face':clean,'hands':[],'pose':None,'headPoseFiltered':data.get('headPoseFiltered') is True,'timestamp':time.time()*1000}
        return {'ok':True}

    async def chat(self,request:Request):
        if self.edition=='vtuber' or self.state.get('edition')=='vtuber':return JSONResponse({'error':'Open Sakura Companion on the PC for chat.'},409)
        body=await request.json();text=str(body.get('text','')).strip()[:4000]
        if not text:return JSONResponse({'error':'Enter a message'},400)
        async with httpx.AsyncClient(timeout=120) as client:
            response=await client.post(f'http://127.0.0.1:{self.pc_port}/api/chat',json={'text':text,'defer_audio':True})
            if not response.is_success:return JSONResponse({'error':'PC companion could not reply. Check its AI settings.'},response.status_code)
            reply=response.json().get('reply','')
            with self.lock:self.commands.append({'type':'phone-reply','text':reply})
            return {'reply':reply}

    async def gemini(self,request:Request):
        if self.edition=='vtuber' or self.state.get('edition')=='vtuber':return JSONResponse({'error':'Use Sakura Companion on the PC.'},409)
        body=await request.json();key=str(body.get('key','')).strip()
        payload={'llm_provider':'gemini'}
        if key:payload['gemini_api_key']=key
        async with httpx.AsyncClient(timeout=30) as client:
            response=await client.post(f'http://127.0.0.1:{self.pc_port}/api/settings',json=payload)
            if not response.is_success:return JSONResponse({'error':'Could not configure Gemini on the PC.'},response.status_code)
        return {'ok':True}

    def poll(self,state):
        with self.lock:
            self.state=state;commands=list(self.commands);self.commands.clear();frame=self.frame;self.frame=None
            camera=self.camera;self.camera=None
        if camera and time.time()-camera['timestamp']>4:camera=None
        return {'enabled':self.enabled,'commands':commands,'frame':frame,'camera':camera}

link=MobileLink()
