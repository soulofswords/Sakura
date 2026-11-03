"""Phone deck slots are bound on the PC; the phone cannot supply commands."""
import base64
import hashlib
import json
from pathlib import Path
import secrets
import threading
from atomic_state import state_lock,atomic_text

POSES={'greeting_wave','hands_both','hand_left','hand_right','groove','step','wave','twist','disco','march','stop'}
LOCK=threading.Lock()

def read(root):
    try:return validate(json.loads((Path(root)/'desktop-profile/hotkey-deck.json').read_text(encoding='utf-8')))
    except (OSError,ValueError,TypeError):return {'slots':[],'port':4455}

def validate(value):
    if not isinstance(value,dict) or type(value.get('port',4455)) is not int or not 1024<=value.get('port',4455)<=65535:raise ValueError('Use a valid local OBS WebSocket port.')
    slots=value.get('slots',[])
    if not isinstance(slots,list) or len(slots)>24:raise ValueError('A hotkey deck supports up to 24 buttons.')
    clean=[];seen=set()
    for slot in slots:
        if not isinstance(slot,dict):raise ValueError('Invalid hotkey button.')
        identifier=slot.get('id');label=slot.get('label');kind=slot.get('kind');target=slot.get('target')
        if not isinstance(identifier,str) or not identifier.isalnum() or len(identifier)>40 or identifier in seen:raise ValueError('Each button needs a unique alphanumeric ID.')
        if not isinstance(label,str) or not 1<=len(label.strip())<=60:raise ValueError('Give each button a short label.')
        if kind not in ('scene','pose') or not isinstance(target,str) or not 1<=len(target)<=200 or any(ord(c)<32 for c in target):raise ValueError('Choose an OBS scene or avatar pose.')
        if kind=='pose' and target not in POSES:raise ValueError('Choose a supported pose.')
        seen.add(identifier);clean.append({'id':identifier,'label':label.strip(),'kind':kind,'target':target})
    return {'slots':clean,'port':value.get('port',4455)}

def configure(root,payload):
    from agent_connections import secret_set
    value=validate(payload);password=payload.get('password')
    if password is not None and (not isinstance(password,str) or len(password)>500):raise ValueError('Invalid OBS password.')
    path=Path(root)/'desktop-profile/hotkey-deck.json'
    with state_lock(path):atomic_text(path,json.dumps(value))
    if password:secret_set('obs-deck',{'password':password})
    return value

def obs_request(root,kind,data=None):
    from agent_connections import secret_get
    from websockets.sync.client import connect
    config=read(root);request_id=secrets.token_hex(12)
    try:
        with connect('ws://127.0.0.1:'+str(config['port']),open_timeout=3,close_timeout=1,max_size=1024**2) as ws:
            hello=json.loads(ws.recv(timeout=5))
            if hello.get('op')!=0:raise ValueError('OBS WebSocket did not send a valid greeting.')
            auth=hello.get('d',{}).get('authentication');identify={'rpcVersion':1}
            if auth:
                password=secret_get('obs-deck').get('password','')
                secret=base64.b64encode(hashlib.sha256((password+auth['salt']).encode()).digest()).decode()
                identify['authentication']=base64.b64encode(hashlib.sha256((secret+auth['challenge']).encode()).digest()).decode()
            ws.send(json.dumps({'op':1,'d':identify}))
            if json.loads(ws.recv(timeout=5)).get('op')!=2:raise ValueError('OBS rejected authentication.')
            ws.send(json.dumps({'op':6,'d':{'requestType':kind,'requestId':request_id,'requestData':data or {}}}))
            for _ in range(20):
                reply=json.loads(ws.recv(timeout=5))
                if reply.get('op')==7 and reply.get('d',{}).get('requestId')==request_id:
                    result=reply['d']
                    if not result.get('requestStatus',{}).get('result'):raise ValueError('OBS could not complete the scene action. Check that the scene exists.')
                    return result.get('responseData',{})
            raise ValueError('No OBS response was received.')
    except ValueError:raise
    except Exception:raise ValueError('Could not connect to OBS on this PC. Enable OBS WebSocket and check the saved port/password.') from None

def execute(root,identifier):
    if not LOCK.acquire(blocking=False):raise ValueError('Wait for the previous deck action.')
    try:
        slot=next((s for s in read(root)['slots'] if s['id']==identifier),None)
        if not slot:raise ValueError('This button was removed or has not been configured on the PC.')
        if slot['kind']=='scene':obs_request(root,'SetCurrentProgramScene',{'sceneName':slot['target']});return {'ok':True,'scene':slot['target']}
        return {'ok':True,'pose':slot['target']}
    finally:LOCK.release()
