"""Opt-in LAN relay: exposes only paired phone controls, never the PC API."""
import asyncio
import os
import ipaddress
import secrets
import socket
import select
import platform
import threading
import time
import hashlib
import hmac
import json
import re
from pathlib import Path
from collections import deque
import httpx
from local_api_security import internal_headers
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse,FileResponse
import uvicorn
import mobile_tls

DISCOVERY_MAGIC=b'sakura-discover-v1'
DISCOVERY_PORT=8770

class MobileLink:
    def __init__(self,store_path=None):
        self.enabled=False;self.code='';self.tokens=set();self.commands=deque(maxlen=50)
        from product import EDITION
        from config import BASE_DIR
        self.store=Path(store_path) if store_path else BASE_DIR/'phone-devices.json'
        from vtuber_instances import instance_index
        slot=instance_index() if EDITION=='vtuber' or os.environ.get('SAKURA_VTUBER_INSTANCE')=='1' else 1
        if store_path is None and slot>1:
            self.store=BASE_DIR/f'desktop-profile-{slot}'/'phone-devices.json'
            self.store.parent.mkdir(parents=True,exist_ok=True)
        self.identity_file=self.store.with_name('phone-link-id.txt')
        self.pc_id=self._load_identity();self.pc_name=(platform.node() or 'Sakura PC')[:60]+(f' · VTuber {slot}' if slot>1 else '')
        self.discovery_port=DISCOVERY_PORT;self.beacon_sockets=[];self.beacon_thread=None;self.beacon_stop=None;self.beacon_replies=[]
        self.identity_attempts={}
        self.tracking_arrivals=deque(maxlen=240)
        try:self.devices=json.loads(self.store.read_text(encoding='utf-8'))
        except (OSError,ValueError):self.devices={}
        if not isinstance(self.devices,dict):self.devices={}
        self.devices={key:value for key,value in self.devices.items() if isinstance(key,str) and isinstance(value,dict)
            and re.fullmatch(r'[0-9a-f]{64}',str(value.get('token_hash','')))}
        self.edition=EDITION;self.frame=None;self.camera=None;self.state={'edition':EDITION};self.lock=threading.RLock();self.server=None;self.attempts={};self.last_contact=0;self.contact_kind='';self.contact_host='';self.own_addresses=set();self._tls=None
        self.pc_port=8766;self.port=(8772 if slot==1 else 8810+slot) if EDITION=='vtuber' else (8771 if slot==1 else 8820+slot);self.code_expires=0;self.thread=None
        self.model_transfer=None;self.model_package=None;self.transfer_request=None;self.tracking_control=None;self.tracking_sequence=0
        self.api=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
        self.api.add_api_route('/pair',self.pair,methods=['POST'])
        self.api.add_api_route('/identity-proof',self.identity_proof,methods=['POST'])
        self.api.add_api_route('/state',self.phone_state,methods=['GET'])
        self.api.add_api_route('/tools',self.device_tools,methods=['POST'])
        self.api.add_api_route('/model/package/{identifier}',self.download_model,methods=['GET'])
        self.api.add_api_route('/command',self.command,methods=['POST'])
        self.api.add_api_route('/frame',self.tracking_frame,methods=['POST'])
        self.api.add_api_route('/camera',self.camera_frame,methods=['POST'])
        self.api.add_api_route('/chat',self.chat,methods=['POST'])
        self.api.add_api_route('/gemini',self.gemini,methods=['POST'])
        self.api.middleware('http')(self.guard)

    def contact(self,kind,host):
        # This PC answering its own probe, or talking to itself, is not proof that a phone
        # arrived, and the panel goes on to claim exactly that, so only count foreign hosts.
        if host.startswith('127.') or host in self.own_addresses:return
        self.last_contact=time.time();self.contact_kind=kind;self.contact_host=host

    async def guard(self,request,call_next):
        host=request.client.host if request.client else ''
        try:private=any(ipaddress.ip_address(host) in ipaddress.ip_network(net) for net in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','127.0.0.0/8','::1/128'))
        except ValueError:private=False
        if not self.enabled or not private:return JSONResponse({'error':'Phone link is off.'},403)
        # Whether the phone ever arrived is the difference between a wrong code and a
        # network that cannot see this PC, so remember the last time anything did.
        # Record authenticated contacts below, not untrusted traffic.
        # A chunked body has no Content-Length, so demand one before reading anything.
        if request.method in ('POST','PUT','PATCH'):
            try:length=int(request.headers.get('content-length',''))
            except (TypeError,ValueError):return JSONResponse({'error':'A Content-Length header is required.'},411)
            if length>250000:return JSONResponse({'error':'Request too large'},413)
        elif int(request.headers.get('content-length','0') or 0)>250000:return JSONResponse({'error':'Request too large'},413)
        if request.url.path not in ('/pair','/identity-proof'):
            token=request.headers.get('authorization','').removeprefix('Bearer ')
            digest=hashlib.sha256(token.encode()).hexdigest()
            with self.lock:device=next((d for d in self.devices.values() if secrets.compare_digest(str(d.get('token_hash','')),digest)),None)
            if device is not None and device.get('expires_at',0)<=time.time():return JSONResponse({'error':'Pairing expired. Pair this phone again.'},401)
            if not token or (token not in self.tokens and device is None):return JSONResponse({'error':'Pair with the PC first.'},401)
            if device is not None:device['last_seen']=time.time()
        if request.url.path not in ('/pair','/identity-proof'):self.contact('request',host)
        return await call_next(request)

    def _load_identity(self):
        # A random id saved beside the device list is what lets a phone keep its
        # pairing after the router hands this PC a different address.
        try:
            stored=self.identity_file.read_text(encoding='utf-8').strip()
            if re.fullmatch(r'[0-9a-f]{32}',stored):return stored
        except OSError:pass
        generated=secrets.token_hex(16)
        try:self.identity_file.parent.mkdir(parents=True,exist_ok=True);self.identity_file.write_text(generated,encoding='utf-8')
        except OSError:pass
        return generated

    @property
    def tls(self):
        with self.lock:
            if self._tls is None:self._tls=mobile_tls.ensure_identity(self.store.parent)
        return self._tls

    def lan_addresses(self):
        addresses=set()
        try:
            for entry in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET):
                address=entry[4][0]
                if ipaddress.ip_address(address).is_private and not address.startswith('127.'):addresses.add(address)
        except OSError:pass
        return sorted(addresses)

    def start_beacon(self):
        self.stop_beacon()
        sockets=[]
        addresses=self.lan_addresses();self.own_addresses=set(addresses)
        for address in addresses:
            try:
                probe=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
                probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                probe.setblocking(False);probe.bind((address,self.discovery_port));sockets.append(probe)
            except OSError:
                probe.close()
        self.beacon_sockets=sockets;self.beacon_stop=threading.Event()
        self.beacon_thread=threading.Thread(target=self.beacon_loop,args=(sockets,self.beacon_stop),daemon=True,name='sakura-discovery')
        self.beacon_thread.start()

    def stop_beacon(self):
        stop=self.beacon_stop;self.beacon_stop=None
        if stop:stop.set()
        sockets,self.beacon_sockets=self.beacon_sockets,[]
        for probe in sockets:
            try:probe.close()
            except OSError:pass
        thread=self.beacon_thread;self.beacon_thread=None
        if thread and thread.is_alive():thread.join(timeout=1.5)

    def discovery_reply(self,data,host,sender=None):
        # A flooded probe still must not starve the phone's HTTP pairing calls.
        if not self.enabled or data.strip()!=DISCOVERY_MAGIC:return None
        if sender:
            try:
                if not any(ipaddress.ip_address(sender) in ipaddress.ip_network(net) for net in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','127.0.0.0/8')):return None
            except ValueError:return None
        now=time.time()
        self.beacon_replies=[entry for entry in self.beacon_replies if isinstance(entry,tuple) and now-entry[1]<1]
        if sum(peer==sender for peer,stamp in self.beacon_replies)>=10 or len(self.beacon_replies)>=200:return None
        self.beacon_replies.append((sender,now))
        # The phone pins this certificate before it sends the pairing code, so a
        # spoofed beacon cannot read the code or impersonate this PC later.
        return json.dumps({'service':'sakura','id':self.pc_id,'name':self.pc_name,'edition':self.edition,
            'https':f'https://{host}:{self.port}','port':self.port,'fingerprint':self.tls['fingerprint']}).encode()

    def beacon_loop(self,sockets,stop):
        addresses=tuple(self.lan_addresses());self.own_addresses=set(addresses);next_refresh=time.monotonic()+2
        while not stop.is_set() and self.enabled:
            if time.monotonic()>=next_refresh:
                current=tuple(self.lan_addresses());self.own_addresses=set(current);next_refresh=time.monotonic()+2
                if current!=addresses or not sockets:
                    for probe in sockets:
                        try:probe.close()
                        except OSError:pass
                    sockets[:]=[]
                    for address in current:
                        probe=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
                        try:
                            probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                            probe.setblocking(False);probe.bind((address,self.discovery_port));sockets.append(probe)
                        except OSError:probe.close()
                    addresses=current
            if not sockets:
                stop.wait(.4);continue
            try:readable,_,_=select.select(sockets,[],[],0.4)
            except (OSError,ValueError):
                if stop.is_set():return
                next_refresh=0;continue
            for probe in readable:
                try:data,sender=probe.recvfrom(512)
                except OSError:continue
                reply=self.discovery_reply(data,probe.getsockname()[0],sender[0])
                if reply is None:continue
                try:probe.sendto(reply,sender)
                except OSError:pass

    async def identity_proof(self,request:Request):
        now=time.monotonic();host=request.client.host
        recent=[stamp for stamp in self.identity_attempts.get(host,[]) if now-stamp<60]
        if len(recent)>=30:return JSONResponse({'error':'Too many identity checks. Retry in a minute.'},429)
        recent.append(now);self.identity_attempts[host]=recent
        body=await request.json()
        nonce=str(body.get('nonce',''));device_id=str(body.get('device_id',''))
        endpoint=str(body.get('endpoint',''))
        # Bind proof to this server address: a spoofed beacon must not relay a
        # challenge to the real PC and pass its answer off as its own.
        if request.url.hostname not in self.lan_addresses() or endpoint!=f'{request.url.scheme}://{request.url.hostname}:{self.port}':
            return JSONResponse({'error':'Identity endpoint does not match this PC.'},400)
        if not re.fullmatch(r'[0-9a-f]{64}',nonce) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',device_id):
            return JSONResponse({'error':'Invalid identity challenge.'},400)
        with self.lock:device=self.devices.get(device_id)
        if not device:return JSONResponse({'error':'Pair this phone first.'},401)
        key=bytes.fromhex(device['token_hash'])
        proof=hmac.new(key,(self.pc_id+'\n'+endpoint+'\n'+nonce).encode(),hashlib.sha256).hexdigest()
        return {'pc_id':self.pc_id,'endpoint':endpoint,'nonce':nonce,'proof':proof}

    def start(self,pc_port):
        self.pc_port=pc_port
        if not self.enabled:
            self.enabled=True;self.code=f'{secrets.randbelow(1000000):06d}';self.code_expires=time.time()+300
            identity=self.tls
            self.server=uvicorn.Server(uvicorn.Config(self.api,host='0.0.0.0',port=self.port,
                ssl_certfile=identity['cert'],ssl_keyfile=identity['key'],log_level='warning',access_log=False))
            if self.thread and self.thread.is_alive():self.thread.join(timeout=2)
            self.thread=threading.Thread(target=self.server.run,daemon=True);self.thread.start()
            self.start_beacon()
        return self.info()

    def info(self):
        # A record saved before pairings carried an expiry is refused by guard(), so the
        # panel must not call it "Remembered" and invite a tap that can only fail.
        with self.lock:devices=[{'id':id,'name':device.get('name','Android device'),'connected':self.enabled and time.time()-device.get('last_seen',0)<15,'pairable':device.get('expires_at',0)>time.time()} for id,device in self.devices.items()]
        # /pair rejects an expired code, so the settings panel must never present one as live:
        # a box full of digits the phone will refuse is worse than an empty box that says why.
        live=self.enabled and time.time()<self.code_expires
        return {'enabled':self.enabled,'code':self.code if live else '','code_expired':bool(self.enabled and not live),
                'contact_age':round(time.time()-self.last_contact) if self.last_contact else None,
                'contact_kind':self.contact_kind,'contact_host':self.contact_host,
                'addresses':[f'https://{ip}:{self.port}' for ip in self.lan_addresses()],'port':self.port,'paired':len(self.tokens),
                'id':self.pc_id,'name':self.pc_name,'discovery_port':self.discovery_port,'devices':devices,
                'fingerprint':self.tls['fingerprint']}

    def save_devices(self):
        with self.lock:
            self.store.parent.mkdir(parents=True,exist_ok=True)
            pending=self.store.with_suffix('.tmp');pending.write_text(json.dumps(self.devices,indent=2),encoding='utf-8');pending.replace(self.store)

    def forget_device(self,device_id):
        with self.lock:
            removed=self.devices.pop(device_id,None)
            if removed:self.tokens={token for token in self.tokens if hashlib.sha256(token.encode()).hexdigest()!=removed.get('token_hash')}
            self.save_devices()
        return self.info()

    def new_pairing_code(self):
        if not self.enabled:raise ValueError('Enable phone connection first.')
        self.code=f'{secrets.randbelow(1000000):06d}';self.code_expires=time.time()+300
        return self.info()

    def stop(self):
        self.enabled=False;self.tokens.clear();self.code='';self.frame=None;self.camera=None;self.commands.clear();self.transfer_request=None
        self.stop_beacon()
        if self.server:self.server.should_exit=True

    async def pair(self,request:Request):
        host=request.client.host;now=time.time()
        global_attempts=[stamp for stamp in self.attempts.get('*',[]) if now-stamp<60]
        if len(global_attempts)>=15:return JSONResponse({'error':'Too many pairing attempts. Wait one minute.'},429)
        global_attempts.append(now);self.attempts['*']=global_attempts
        attempts=[stamp for stamp in self.attempts.get(host,[]) if now-stamp<60]
        if len(attempts)>=5:return JSONResponse({'error':'Too many attempts. Wait one minute.'},429)
        attempts.append(now);self.attempts[host]=attempts
        body=await request.json()
        if now>self.code_expires or not secrets.compare_digest(str(body.get('code','')),self.code):
            return JSONResponse({'error':'Pairing code is wrong or expired. Turn phone link off and on.'},401)
        token=secrets.token_urlsafe(32)
        device_id=str(body.get('device_id') or secrets.token_hex(16))[:64]
        if not re.fullmatch(r'[A-Za-z0-9_-]+',device_id):return JSONResponse({'error':'Invalid device identifier'},400)
        if device_id not in self.devices and len(self.devices)>=32:return JSONResponse({'error':'Forget an old device before adding another.'},409)
        with self.lock:
            self.devices[device_id]={'name':str(body.get('device_name') or 'Android device')[:80],
                'token_hash':hashlib.sha256(token.encode()).hexdigest(),'last_seen':now,'expires_at':now+30*86400}
            self.save_devices()
            self.contact('paired',host)
            self.code='';self.code_expires=0
        # The phone records this fingerprint with the token and rejects any other
        # certificate on reconnect, so a later LAN impostor cannot collect frames.
        return {'token':token,'id':self.pc_id,'name':self.pc_name,'edition':self.state.get('edition','companion'),
            'fingerprint':self.tls['fingerprint']}

    async def device_tools(self,request:Request):
        body=await request.json()
        if body.get('action') not in ('system.status','audio.volume','clipboard.read','clipboard.write'):
            return JSONResponse({'error':'Unsupported PC tool.'},400)
        payload={k:body[k] for k in ('action','operation','value','text') if k in body};payload['phone']=True
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response=await client.post(f'http://127.0.0.1:{self.pc_port}/api/assistant-tools/device',json=payload,headers=internal_headers())
                return JSONResponse(response.json(),response.status_code)
        except (httpx.HTTPError,ValueError):return JSONResponse({'error':'PC tool unavailable. Retry when Sakura is ready.'},503)

    def control_tracking(self, payload):
        if not self.enabled or not self.devices:raise ValueError('Enable Connect to Phone and pair Sakura Mobile first.')
        action=payload.get('action')
        if action not in ('start','stop','calibrate','hands'):raise ValueError('Unsupported tracking action')
        if action=='hands' and type(payload.get('enabled')) is not bool:raise ValueError('Hand tracking enabled must be a boolean')
        with self.lock:
            self.tracking_sequence+=1
            self.tracking_control={'id':self.tracking_sequence,'action':action,'enabled':payload.get('enabled') if action=='hands' else None,'expires':time.time()+15}
        return {'ok':True}

    async def phone_state(self):
        # The id lets a phone that reached this address confirm it is the same PC it
        # paired with, and refresh its saved address after a DHCP change.
        return {**self.state,'pc_id':self.pc_id,'name':self.pc_name,'model_transfer':self.model_transfer,'transfer_request':self.transfer_request,
            'tracking_control':self.tracking_control,'fingerprint':self.tls['fingerprint']}

    def transfer_result(self,identifier,status,error=''):
        if status not in ('preparing','cancelled','failed'):raise ValueError('Invalid transfer status.')
        with self.lock:
            if not self.transfer_request or self.transfer_request['id']!=identifier:raise ValueError('This model request has expired.')
            self.transfer_request.update(status=status,error=str(error)[:240])
        return {'ok':True}

    def stage_selection(self,source,folder,kind,request_id):
        if not self.enabled:raise ValueError('Phone connection is off.')
        from config import BASE_DIR
        from mobile_models import bundle_selected_folder
        self.transfer_result(request_id,'preparing')
        metadata,path=bundle_selected_folder(source,folder,kind,BASE_DIR/'mobile-transfer-cache')
        with self.lock:
            if not self.transfer_request or self.transfer_request['id']!=request_id:
                path.unlink(missing_ok=True);raise ValueError('This model request has expired.')
            old=self.model_package;self.model_package=path;self.model_transfer=metadata
            self.transfer_request.update(status='ready',model=metadata)
        if old:old.unlink(missing_ok=True)
        return metadata

    def stage_model(self,url):
        if not self.enabled:raise ValueError('Enable Connect to Phone and pair your phone first.')
        from config import MODELS_DIR,BASE_DIR
        from mobile_models import bundle_model
        metadata,path=bundle_model(url,MODELS_DIR,BASE_DIR/'mobile-transfer-cache')
        with self.lock:
            old=self.model_package;self.model_transfer=metadata;self.model_package=path
        if old:old.unlink(missing_ok=True)
        return metadata

    async def download_model(self,identifier:str):
        with self.lock:metadata=self.model_transfer;path=self.model_package
        if not metadata or identifier!=metadata['id'] or not path or not path.is_file():return JSONResponse({'error':'No current model transfer. Send the model again from the PC.'},404)
        return FileResponse(path,media_type='application/zip',filename='Sakura-model.zip')

    async def command(self,request:Request):
        body=await request.json();kind=body.get('type')
        if kind=='model-result':
            with self.lock:
                current=self.transfer_request
                if not current or current['id']!=str(body.get('request_id','')) or current.get('model',{}).get('id')!=str(body.get('model_id','')):
                    return JSONResponse({'error':'The model transfer has expired.'},409)
                status=body.get('status')
                if status not in ('received','failed'):return JSONResponse({'error':'Invalid transfer result.'},400)
                if current.get('status') not in ('ready','received'):return JSONResponse({'error':'This transfer is no longer active.'},409)
                current.update(status=status,error=str(body.get('error',''))[:240])
            return {'ok':True}
        if kind=='cancel-model':
            with self.lock:
                identifier=str(body.get('request_id',''))
                if self.transfer_request and self.transfer_request['id']==identifier:
                    self.transfer_request.update(status='cancelled')
                    self.commands=deque((c for c in self.commands if c.get('request_id')!=identifier),maxlen=50)
            return {'ok':True}
        if kind=='request-model':
            with self.lock:
                if self.transfer_request and self.transfer_request.get('status') in ('waiting','preparing') and time.time()-self.transfer_request.get('created',0)<600:
                    return JSONResponse({'error':'A model transfer is already pending on the PC.'},409)
                identifier=secrets.token_hex(16)
                self.transfer_request={'id':identifier,'status':'waiting','created':time.time()}
                self.commands.append({'type':'request-model','request_id':identifier})
            return {'request_id':identifier}
        if kind not in ('expression','clear-expressions','tracking-start','tracking-stop','companion-tracking-start','companion-tracking-stop','camera-start','camera-stop','calibrate'):
            return JSONResponse({'error':'Unsupported control'},400)
        if kind.startswith('companion-tracking-') and (self.edition=='vtuber' or self.state.get('edition')=='vtuber'):
            return JSONResponse({'error':'Companion camera tracking needs Sakura Companion.'},409)
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
        if matrix is not None and (not isinstance(matrix,list) or len(matrix)!=16 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in matrix)):
            return JSONResponse({'error':'Invalid face pose'},400)
        landmarks=face.get('landmarks',[]);blendshapes=face.get('blendshapes',[])
        if not isinstance(landmarks,list) or len(landmarks)>500 or not isinstance(blendshapes,list) or len(blendshapes)>100:
            return JSONResponse({'error':'Invalid face signals'},400)
        if any(not isinstance(p,dict) or any(not isinstance(p.get(k),(int,float)) or not math.isfinite(p[k]) for k in ('x','y','z')) for p in landmarks):
            return JSONResponse({'error':'Invalid face landmarks'},400)
        if any(not isinstance(p,dict) or not isinstance(p.get('categoryName'),str) or not isinstance(p.get('score'),(int,float)) or not math.isfinite(p['score']) for p in blendshapes):
            return JSONResponse({'error':'Invalid face blendshapes'},400)
        clean={'matrix':matrix,'landmarks':landmarks,'blendshapes':blendshapes}
        camera=data.get('cameraFrame')
        if camera is not None:
            import base64,binascii
            try:
                if not isinstance(camera,dict):raise ValueError()
                width,height=camera.get('width'),camera.get('height')
                if type(width) is not int or type(height) is not int or not 1<=width<=960 or not 1<=height<=960:raise ValueError()
                image=camera.get('image')
                if not isinstance(image,str) or len(image)>140000:raise ValueError()
                jpeg=base64.b64decode(image,validate=True)
                if not jpeg.startswith(b'\xff\xd8\xff'):raise ValueError()
            except (ValueError,binascii.Error):return JSONResponse({'error':'Invalid tracking camera image'},400)
            if self.state.get('tracking_face_source')=='nvidia_ar':
                from nvidia_ar_tracker import tracker
                if tracker.snapshot()['running']:
                    tracker.submit_frame(jpeg,width,height)
        # Every packet uses the same selected expression source, including packets
        # without a JPEG. The tracker expires results when inference stops.
        if self.state.get('tracking_face_source')=='nvidia_ar':
            from nvidia_ar_tracker import tracker
            shapes=tracker.snapshot().get('blendshapes',{})
            clean['blendshapes']=[{'categoryName':k,'score':v} for k,v in shapes.items()]

        def points(value, count):
            return isinstance(value,list) and len(value)==count and all(isinstance(p,dict)
                and all(type(p.get(k)) in (int,float) and math.isfinite(p[k]) for k in ('x','y','z'))
                and ('visibility' not in p or type(p['visibility']) in (int,float) and math.isfinite(p['visibility'])) for p in value)
        hands=data.get('hands',[]);pose=data.get('pose')
        if not isinstance(hands,list) or len(hands)>2:
            return JSONResponse({'error':'Invalid hand signals'},400)
        for hand in hands:
            if (not isinstance(hand,dict) or hand.get('side') not in ('Left','Right','left','right')
                or not points(hand.get('landmarks'),21)
                or hand.get('world') is not None and not points(hand['world'],21)
                or type(hand.get('confidence',1)) not in (int,float)
                or not math.isfinite(hand.get('confidence',1)) or not 0<=hand.get('confidence',1)<=1):
                return JSONResponse({'error':'Invalid hand landmarks'},400)
        if pose is not None and (not isinstance(pose,dict) or not points(pose.get('landmarks'),33)
            or pose.get('world') is not None and not points(pose['world'],33)):
            return JSONResponse({'error':'Invalid body pose'},400)
        enabled=data.get('handTrackingEnabled',True) is not False
        reported=data.get('trackingMetrics',{})
        if not isinstance(reported,dict):reported={}
        metrics={}
        for key,limit in [('sequence',9007199254740991),('cameraFps',240),('processedFps',240),('uploadedFps',240),('processingMs',10000)]:
            value=reported.get(key)
            if type(value) in (int,float) and math.isfinite(value) and 0<=value<=limit:metrics[key]=value
        with self.lock:
            now=time.monotonic();self.tracking_arrivals.append(now)
            while self.tracking_arrivals and now-self.tracking_arrivals[0]>1:self.tracking_arrivals.popleft()
            metrics['receivedFps']=len(self.tracking_arrivals)
            self.frame={'face':clean,'hands':hands if enabled else [],'pose':pose,
                'handTrackingEnabled':enabled,'headPoseFiltered':data.get('headPoseFiltered') is True,'timestamp':time.time()*1000,'trackingMetrics':metrics}
        return {'ok':True}

    async def chat(self,request:Request):
        if self.edition=='vtuber' or self.state.get('edition')=='vtuber':return JSONResponse({'error':'Open Sakura Companion on the PC for chat.'},409)
        body=await request.json();text=str(body.get('text','')).strip()[:4000]
        if not text:return JSONResponse({'error':'Enter a message'},400)
        async with httpx.AsyncClient(timeout=120) as client:
            response=await client.post(f'http://127.0.0.1:{self.pc_port}/api/chat',json={'text':text,'defer_audio':True,'phone':True},headers=internal_headers())
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
            response=await client.post(f'http://127.0.0.1:{self.pc_port}/api/settings',json=payload,headers=internal_headers())
            if not response.is_success:return JSONResponse({'error':'Could not configure Gemini on the PC.'},response.status_code)
        return {'ok':True}

    def poll(self,state):
        with self.lock:
            self.state=state;commands=list(self.commands);self.commands.clear();frame=self.frame;self.frame=None
            camera=self.camera;self.camera=None
            connected=self.enabled and any(time.time()-device.get('last_seen',0)<15 for device in self.devices.values())
        if camera and time.time()-camera['timestamp']>4:camera=None
        return {'enabled':self.enabled,'connected':connected,'commands':commands,'frame':frame,'camera':camera}

link=MobileLink()
