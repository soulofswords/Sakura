import hashlib
import hmac
import json
import queue
import re
import threading
import time
from pathlib import Path

import requests

from credentials import get_cloud_key,set_cloud_key


PLATFORMS=('discord','slack','whatsapp')
ROOTS={'discord':'https://discord.com/api/v10','slack':'https://slack.com/api','whatsapp':'https://graph.facebook.com/v23.0'}


def identifiers(value,platform):
    if isinstance(value,str):value=value.replace(',',' ').split()
    if not isinstance(value,list) or len(value)>10:raise ValueError('Enter up to 10 allowed IDs.')
    pattern=r'[A-Z][A-Z0-9]{5,30}' if platform=='slack' else r'[0-9]{5,25}'
    if any(not isinstance(item,str) or not re.fullmatch(pattern,item) for item in value):raise ValueError('Enter exact provider IDs, not display names.')
    return sorted(set(value))


class MessagingGateway:
    def __init__(self,platform,path,handler):
        if platform not in PLATFORMS:raise ValueError('Unsupported messaging provider.')
        self.platform=platform;self.path=Path(path);self.handler=handler
        self.lock=threading.RLock();self.control=threading.RLock();self.stop_event=threading.Event();self.thread=None
        self.enabled=False;self.channels=[];self.users=[];self.phone_id='';self.last_error='';self.offsets={};self.seen=[]
        self.queue=queue.Queue(maxsize=20);self.channel_index=0;self.worker=threading.local()

    def _secret(self,suffix=''):return get_cloud_key('agent_'+self.platform+suffix)

    def _save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'enabled':self.enabled,'channels':self.channels,'users':self.users,'phone_id':self.phone_id,'seen':self.seen[-1000:]}),encoding='utf-8')
        temporary.replace(self.path)

    def restore(self):
        try:data=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError):data={}
        if not isinstance(data,dict):raise ValueError('Invalid gateway settings.')
        with self.lock:
            self.channels=identifiers(data.get('channels',[]),self.platform);self.users=identifiers(data.get('users',[]),self.platform)
            self.phone_id=str(data.get('phone_id',''))
            self.seen=[item for item in data.get('seen',[]) if isinstance(item,str) and re.fullmatch(r'[a-f0-9]{64}',item)][-1000:]
            self.enabled=data.get('enabled') is True and bool(self._secret())

    def status(self):
        with self.lock:return {'provider':self.platform,'enabled':self.enabled,'running':bool(self.thread and self.thread.is_alive()),
                               'channels':list(self.channels),'users':list(self.users),'phone_id':self.phone_id,
                               'token_set':bool(self._secret()),'app_secret_set':bool(self._secret('_app_secret')) if self.platform=='whatsapp' else False,
                               'verify_token_set':bool(self._secret('_verify_token')) if self.platform=='whatsapp' else False,'last_error':self.last_error}

    def configure(self,payload):
        if not isinstance(payload,dict) or set(payload)-{'enabled','channels','users','phone_id','token','app_secret','verify_token','clear_token'}:raise ValueError('Unexpected gateway settings.')
        enabled=payload.get('enabled');clear=payload.get('clear_token',False)
        if type(enabled) is not bool or type(clear) is not bool:raise ValueError('Choose whether to enable or remove this gateway.')
        channels=identifiers(payload.get('channels',[]),self.platform);users=identifiers(payload.get('users',[]),self.platform)
        phone=payload.get('phone_id','')
        if not isinstance(phone,str) or (phone and not re.fullmatch(r'[0-9]{5,25}',phone)):raise ValueError('Enter a numeric WhatsApp phone-number ID.')
        secrets={}
        for name in ('token','app_secret','verify_token'):
            value=payload.get(name,'')
            if not isinstance(value,str) or len(value)>2000 or any(ord(c)<33 or ord(c)>126 for c in value):raise ValueError('Paste the provider secret exactly, without spaces or line breaks.')
            if self.platform!='whatsapp' and name!='token' and value:raise ValueError('This provider does not use WhatsApp app secrets.')
            if value:secrets[name]=value
        if clear and (secrets or enabled):raise ValueError('Disable the gateway before removing its secrets.')
        if enabled and (not users or (self.platform!='whatsapp' and not channels)):raise ValueError('Configure both allowed users and channels before enabling this gateway.')
        if enabled and self.platform=='whatsapp' and not phone:raise ValueError('Configure the WhatsApp phone-number ID first.')
        needed=('token','app_secret','verify_token') if self.platform=='whatsapp' else ('token',)
        if enabled and any(not secrets.get(name) and not self._secret('' if name=='token' else '_'+name) for name in needed):raise ValueError('Save all required provider secrets before enabling the gateway.')
        with self.control:
            if not self.stop():raise ValueError('The previous gateway request is still stopping. Retry in a moment.')
            for name in needed:
                slot='agent_'+self.platform+('' if name=='token' else '_'+name)
                if clear:set_cloud_key(slot,'')
                elif name in secrets:set_cloud_key(slot,secrets[name])
            with self.lock:
                self.enabled=enabled;self.channels=channels;self.users=users;self.phone_id=phone;self.last_error='';self.offsets={}
                self._save()
            self.start(restore=False)
        return self.status()

    def start(self,restore=True):
        with self.control:
            if self.thread and self.thread.is_alive():return
            if restore:self.restore()
            if not self.enabled:return
            self.stop_event=threading.Event()
            # The event travels with the worker: after a stalled stop() a fresh, unset event on
            # the instance would otherwise wake that orphan back up and let it answer people.
            self.thread=threading.Thread(target=self._guarded,args=(self.stop_event,),daemon=True,name='Sakura-'+self.platform)
            self.thread.start()

    def _bound(self):
        """The event this thread was started with, or the live one for outside callers."""
        return getattr(self.worker,'event',None) or self.stop_event

    def _guarded(self,event):
        self.worker.event=event
        try:self._loop()
        finally:self.worker.event=None

    def stop(self):
        with self.control:
            self.stop_event.set()
            alive=self.thread is not None and self.thread.is_alive()
            if alive:self.thread.join(timeout=5)
            stuck=alive and self.thread.is_alive()
            # Dropping the reference is what keeps a reconfigure possible: the orphan holds the
            # set event it was started with, so it can no longer send, and keeping the reference
            # would make every later start() a no-op and leave the gateway dark until restart.
            self.thread=None
            while not self.queue.empty():
                try:self.queue.get_nowait()
                except queue.Empty:break
            return not stuck

    def _request(self,method,path,payload=None):
        prefix='Bot ' if self.platform=='discord' else 'Bearer '
        with requests.request(method,ROOTS[self.platform]+'/'+path,headers={'Authorization':prefix+self._secret()},
                              **({'params':payload} if method=='GET' else {'json':payload}),timeout=(5,20),allow_redirects=False) as response:
            if response.status_code!=200 and response.status_code!=201:raise ValueError('Provider returned HTTP '+str(response.status_code)+'.')
            data=response.json()
        if not isinstance(data,(dict,list)) or (self.platform=='slack' and (not isinstance(data,dict) or data.get('ok') is not True)):raise ValueError('Provider refused the gateway request. Check scopes and access on the provider dashboard.')
        return data

    def _send(self,channel,text):
        if self._bound().is_set():return
        if self.platform=='discord':self._request('POST','channels/'+channel+'/messages',{'content':text[:1900],'allowed_mentions':{'parse':[]}})
        elif self.platform=='slack':
            safe=text.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
            self._request('POST','chat.postMessage',{'channel':channel,'text':safe[:3500],'mrkdwn':False,'parse':'none','unfurl_links':False,'unfurl_media':False})
        else:self._request('POST',self.phone_id+'/messages',{'messaging_product':'whatsapp','to':channel,'type':'text','text':{'body':text[:3500],'preview_url':False}})

    def _reply(self,channel,user,text):
        if self._bound().is_set() or user not in self.users or not isinstance(text,str) or not text.strip():return
        if self.platform!='whatsapp' and channel not in self.channels:return
        if text.strip().split()[0] in ('/help','/start'):
            reply='Sakura messaging: independent AI replies only. Desktop files, tools, memory and approvals are not shared.'
        else:
            try:reply=self.handler(text[:8000])
            except Exception:reply='The AI reply failed. Check Sakura on the PC.'
        if not self._bound().is_set():self._send(channel,str(reply)[:3500])

    def poll_once(self):
        if not self.channels:return
        channel=self.channels[self.channel_index%len(self.channels)];self.channel_index+=1
        offset=self.offsets.get(channel)
        if self.platform=='discord':
            messages=self._request('GET','channels/'+channel+'/messages',{'limit':20,**({'after':offset} if offset else {})})
            if not isinstance(messages,list):raise ValueError('Invalid Discord history response.')
            messages=[message for message in messages if isinstance(message,dict) and re.fullmatch(r'[0-9]{5,25}',str(message.get('id','')))]
            messages.sort(key=lambda message:int(message['id']))
            if offset is None:self.offsets[channel]=messages[-1]['id'] if messages else '0';return
            for message in messages:
                if int(message['id'])<=int(self.offsets[channel]):continue
                self.offsets[channel]=message['id']
                author=message.get('author') or {}
                if not isinstance(author,dict) or author.get('bot') or message.get('webhook_id'):continue
                self._reply(channel,str(author.get('id','')),message.get('content'))
        else:
            if offset is None:self.offsets[channel]=str(time.time());return
            data=self._request('GET','conversations.history',{'channel':channel,'oldest':offset,'inclusive':False,'limit':15})
            messages=data.get('messages',[])
            if not isinstance(messages,list):raise ValueError('Invalid Slack history response.')
            messages=[message for message in messages if isinstance(message,dict) and re.fullmatch(r'[0-9]{1,20}\.[0-9]{1,10}',str(message.get('ts','')))]
            messages.sort(key=lambda message:float(message['ts']))
            for message in messages:
                if float(message['ts'])<=float(self.offsets[channel]):continue
                self.offsets[channel]=message['ts']
                if message.get('bot_id') or message.get('subtype'):continue
                self._reply(channel,str(message.get('user','')),message.get('text'))

    def verify_challenge(self,mode,token,challenge):
        secret=self._secret('_verify_token')
        # Bytes, not str: compare_digest raises TypeError for non-ASCII text, which would turn
        # a probe on this unauthenticated path into a 500 instead of a refusal.
        if self.platform!='whatsapp' or not self.enabled or mode!='subscribe' or not secret or not hmac.compare_digest(str(token).encode('utf-8'),secret.encode('utf-8')):raise ValueError('Webhook verification refused.')
        if not isinstance(challenge,str) or not re.fullmatch(r'[0-9]{1,100}',challenge):raise ValueError('Invalid webhook challenge.')
        return challenge

    def accept_webhook(self,body,signature):
        secret=self._secret('_app_secret')
        if self.platform!='whatsapp' or not self.enabled or not secret or len(body)>256000:raise ValueError('Webhook is unavailable.')
        expected='sha256='+hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(signature).encode('utf-8'),expected.encode('utf-8')):raise ValueError('Webhook signature refused.')
        try:data=json.loads(body)
        except ValueError:raise ValueError('Invalid webhook payload.') from None
        if not isinstance(data,dict) or data.get('object')!='whatsapp_business_account':raise ValueError('Invalid webhook object.')
        accepted=[]
        for entry in data.get('entry',[]):
            for change in entry.get('changes',[]):
                value=change.get('value',{})
                if value.get('metadata',{}).get('phone_number_id')!=self.phone_id:continue
                for message in value.get('messages',[]):
                    if not isinstance(message,dict) or message.get('type')!='text' or message.get('from') not in self.users:continue
                    timestamp=str(message.get('timestamp',''))
                    if not timestamp.isdigit() or not -60<=time.time()-int(timestamp)<=300:continue
                    identifier=message.get('id');text=message.get('text',{}).get('body')
                    if not isinstance(identifier,str) or not 1<=len(identifier)<=300 or not isinstance(text,str):continue
                    hashed=hashlib.sha256(identifier.encode()).hexdigest()
                    with self.lock:
                        if hashed in self.seen:continue
                        if self.queue.full():raise ValueError('Gateway queue is full. Retry delivery later.')
                        self.seen=(self.seen+[hashed])[-1000:];self._save()
                        self.queue.put_nowait((message['from'],message['from'],text[:8000]));accepted.append(hashed)
        return {'ok':True,'accepted':len(accepted)}

    def _loop(self):
        while not self._bound().is_set():
            try:
                if self.platform=='whatsapp':
                    try:item=self.queue.get(timeout=1)
                    except queue.Empty:continue
                    self._reply(*item)
                else:self.poll_once()
                self.last_error=''
            except Exception:
                self.last_error='Gateway request failed. Check credentials, scopes, provider limits and network; failed replies are not resent automatically.'
            if self.platform!='whatsapp':self._bound().wait(60 if self.platform=='slack' else 5)


class MessagingGateways:
    def __init__(self,root,handler):self.items={name:MessagingGateway(name,Path(root)/('gateway-'+name+'.json'),handler) for name in PLATFORMS}
    def get(self,name):
        if name not in self.items:raise ValueError('Choose Discord, Slack or WhatsApp.')
        return self.items[name]
    def status(self):return [item.status() for item in self.items.values()]
    def start(self):
        for item in self.items.values():
            try:item.start()
            except Exception:item.last_error='Gateway could not start. Review local settings.'
    def stop(self):
        for item in self.items.values():item.stop()
