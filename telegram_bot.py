"""Allow-listed Telegram messaging with protected credentials."""
import json
import re
import threading
import time
from pathlib import Path

import requests

from config import BASE_DIR

API = 'https://api.telegram.org'
MAX_MESSAGE = 4000
POLL_SECONDS = 25


def parse_chat_ids(value):
    if value is None:return set()
    if isinstance(value,str):value=value.replace(',', ' ').split()
    if not isinstance(value,(list,tuple,set)) or len(value)>20:raise ValueError('List up to 20 allowed Telegram chat IDs.')
    result=set()
    for item in value:
        try:number=int(str(item).strip())
        except (TypeError,ValueError):raise ValueError('Telegram chat IDs are numbers. Send the bot a message to learn yours.') from None
        if number==0 or abs(number)>=2**52:raise ValueError('Enter a valid nonzero Telegram chat ID.')
        result.add(number)
    return result


class TelegramGateway:
    STOP_TIMEOUT=5
    def __init__(self,store_path=None,handler=None):
        self.store_path=Path(store_path or BASE_DIR/'desktop-profile'/'telegram.json')
        self.handler=handler or (lambda text:'No AI model is configured yet.')
        self.lock=threading.RLock();self.control_lock=threading.RLock()
        self.thread=None;self.stop_event=threading.Event()
        self.token='';self.chat_ids=set();self.enabled=False;self.voice_enabled=False;self.transcriber=None
        self.offset=0;self.last_error='';self.last_message_at=None;self.received=0

    def configure(self,enabled,chat_ids,token=None,clear_token=False,voice_enabled=False):
        from credentials import get_cloud_key,set_cloud_key
        if type(enabled) is not bool or type(clear_token) is not bool:raise ValueError('Choose whether the Telegram gateway is enabled.')
        if type(voice_enabled) is not bool:raise ValueError('Choose whether to transcribe Telegram voice memos.')
        ids=parse_chat_ids(chat_ids)
        if token is not None and not isinstance(token,str):raise ValueError('Enter a Telegram bot token as text.')
        candidate=(token or '').strip()
        if candidate and not re.fullmatch(r'[0-9]{1,20}:[A-Za-z0-9_-]{20,128}',candidate):
            raise ValueError('Enter the bot token exactly as BotFather issued it.')
        if candidate and clear_token:raise ValueError('Choose either a new token or removal, not both.')
        with self.control_lock:
            secret='' if clear_token else candidate or get_cloud_key('telegram')
            if enabled and not secret:raise ValueError('Save a Telegram bot token before enabling the gateway.')
            # An orphan loop still owns the update offset and would acknowledge
            # messages it never replies to, so nothing is rewritten until it is gone.
            if not self.stop():
                raise ValueError('The previous Telegram loop is still stopping. Retry in a moment.')
            if clear_token:set_cloud_key('telegram','')
            elif candidate:set_cloud_key('telegram',candidate)
            self.store_path.parent.mkdir(parents=True,exist_ok=True)
            temporary=self.store_path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'version':1,'enabled':enabled,'chat_ids':sorted(ids),'voice_enabled':voice_enabled}),encoding='utf-8')
            temporary.replace(self.store_path)
            with self.lock:
                if secret!=self.token:self.offset=0
                self.token=secret;self.chat_ids=ids;self.enabled=enabled;self.voice_enabled=voice_enabled;self.last_error=''
            self.restart()
        return self.status()

    def restore(self):
        from credentials import get_cloud_key
        try:payload=json.loads(self.store_path.read_text(encoding='utf-8'))
        except (OSError,ValueError):payload={}
        if not isinstance(payload,dict):raise ValueError('Invalid Telegram gateway settings.')
        with self.lock:
            self.token=get_cloud_key('telegram')
            self.chat_ids=parse_chat_ids(payload.get('chat_ids',[]))
            self.enabled=payload.get('enabled') is True and bool(self.token)
            self.voice_enabled=payload.get('voice_enabled') is True

    def start(self):
        with self.control_lock:
            self.stop()
            self.restore();self.restart()

    def restart(self):
        with self.control_lock:
            self.stop()
            with self.lock:
                if not self.enabled:return
                self.stop_event=threading.Event()
                self.thread=threading.Thread(target=self._poll,args=(self.stop_event,),daemon=True,name='telegram-gateway')
                self.thread.start()

    def stop(self):
        with self.control_lock:
            self.stop_event.set()
            thread=self.thread
            if thread and thread.is_alive():
                if thread is not threading.current_thread():thread.join(timeout=self.STOP_TIMEOUT)
            stopped=not thread or not thread.is_alive()
            # A loop that outlived the join keeps its own set event, so it cannot send
            # a late reply; it is still tracked so a retry cannot start a second poller
            # beside it while it owns the update offset.
            if stopped:self.thread=None
            return stopped

    def status(self):
        from credentials import get_cloud_key
        with self.lock:
            return {'enabled':self.enabled,'running':bool(self.thread and self.thread.is_alive()),
                    'chat_ids':sorted(self.chat_ids),'token_set':bool(get_cloud_key('telegram')),'voice_enabled':self.voice_enabled,
                    'last_error':self.last_error,'last_message_at':self.last_message_at,'received':self.received}

    def _request(self,method,payload,timeout):
        with self.lock:token=self.token
        if not token:raise RuntimeError('Save a Telegram bot token first.')
        with requests.post(f'{API}/bot{token}/{method}',json=payload,timeout=timeout,allow_redirects=False) as response:
            response.raise_for_status()
            body=response.json()
        if not isinstance(body,dict) or body.get('ok') is not True:raise RuntimeError('Telegram refused the request.')
        return body.get('result')

    def voice_text(self,voice):
        from agent_voice import MAX_BYTES,MAX_SECONDS,transcribe
        if not isinstance(voice,dict) or not isinstance(voice.get('file_id'),str) or len(voice['file_id'])>256:raise ValueError('Invalid voice memo.')
        if type(voice.get('duration')) is not int or not 0<voice['duration']<=MAX_SECONDS:raise ValueError('Voice memo is too long.')
        if type(voice.get('file_size')) is not int or not 0<voice['file_size']<=MAX_BYTES:raise ValueError('Voice memo is too large.')
        if self.transcriber is None:raise ValueError('Speech recognition is unavailable.')
        metadata=self._request('getFile',{'file_id':voice['file_id']},20)
        path=metadata.get('file_path','') if isinstance(metadata,dict) else ''
        if not re.fullmatch(r'[A-Za-z0-9_/-]+\.(?:oga|ogg|opus)',path) or '..' in path:raise ValueError('Invalid Telegram voice path.')
        with self.lock:token=self.token
        data=bytearray()
        with requests.get(f'{API}/file/bot{token}/{path}',stream=True,timeout=(5,20),allow_redirects=False) as response:
            if response.status_code!=200:raise ValueError('Voice memo download failed.')
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data)>MAX_BYTES:raise ValueError('Voice memo exceeds the download limit.')
        return transcribe(bytes(data),self.transcriber)

    def reply_for(self,update):
        if not isinstance(update,dict):return None
        message=update.get('message')
        if not isinstance(message,dict):return None
        chat=message.get('chat')
        if not isinstance(chat,dict):return None
        chat_id=chat.get('id');text=message.get('text');voice=message.get('voice')
        if type(chat_id) is not int or (not isinstance(text,str) and not isinstance(voice,dict)):return None
        with self.lock:allowed=chat_id in self.chat_ids
        if not allowed:
            return chat_id,(f'This Sakura bot is private. Your chat ID is {chat_id}. '
                            'Add it under Messaging gateway in the Sakura Agent panel on the PC, then message again.')
        if voice is not None:
            if not self.voice_enabled:return chat_id,'Enable voice memos in the Sakura Telegram gateway settings first.'
            try:text=self.voice_text(voice)
            except Exception:return chat_id,'Voice transcription failed. Use a memo under 4 MB and two minutes; check ffmpeg and speech recognition on the PC.'
        text=text.strip()
        if not text:return None
        if text.split()[0].split('@')[0] in ('/start','/help'):
            return chat_id,'Sakura is connected. Each message gets a separate AI reply. Desktop history, PC files, shell commands and approvals are not available here.'
        try:reply=self.handler(text[:8000])
        except Exception:
            return chat_id,'The AI reply failed. Check the model connection in Sakura on the PC.'
        with self.lock:self.received+=1;self.last_message_at=time.time()
        return chat_id,(str(reply).strip() or 'The model returned an empty reply.')[:MAX_MESSAGE*4]

    def send(self,chat_id,text,stop_event=None):
        for start in range(0,len(text),MAX_MESSAGE):
            if stop_event and stop_event.is_set():return
            self._request('sendMessage',{'chat_id':chat_id,'text':text[start:start+MAX_MESSAGE],'disable_web_page_preview':True},30)

    def poll_once(self,stop_event=None):
        updates=self._request('getUpdates',{'offset':self.offset,'timeout':POLL_SECONDS,'allowed_updates':['message']},POLL_SECONDS+15) or []
        if not isinstance(updates,list):raise ValueError('Invalid Telegram updates.')
        handled=0
        for update in updates:
            if stop_event and stop_event.is_set():break
            if not isinstance(update,dict) or type(update.get('update_id')) is not int:continue
            if update['update_id']<self.offset:continue
            self.offset=update['update_id']+1
            reply=self.reply_for(update)
            if stop_event and stop_event.is_set():break
            if reply:self.send(*reply,stop_event=stop_event);handled+=1
        return handled

    def _poll(self,stop_event):
        while not stop_event.is_set():
            try:
                self.poll_once(stop_event)
                if stop_event.is_set():return
                with self.lock:self.last_error=''
            except requests.HTTPError as error:
                if stop_event.is_set():return
                code=error.response.status_code if error.response is not None else 0
                with self.lock:self.last_error=f'Telegram returned HTTP {code}.'
                if code in (401,404):
                    with self.lock:self.enabled=False
                    return
                stop_event.wait(10)
            except (requests.RequestException,RuntimeError,OSError,ValueError):
                if stop_event.is_set():return
                # Request exceptions can contain the bot token in the URL.
                with self.lock:self.last_error='Telegram connection failed. Check the network and saved bot token.'
                stop_event.wait(5)


gateway=TelegramGateway()
