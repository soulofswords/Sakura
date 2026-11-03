"""Read-only Twitch chat over TLS. No chat posting or moderation commands."""
import hashlib
import re
import socket
import ssl
import threading
import time
from collections import deque
from urllib.parse import urlsplit

NAME=re.compile(r'[a-z0-9_]{1,25}')

def channel_name(link):
    parsed=urlsplit(link)
    if parsed.scheme!='https' or parsed.hostname not in ('twitch.tv','www.twitch.tv') or parsed.username or parsed.password:
        raise ValueError('Use an HTTPS twitch.tv/channel link.')
    name=parsed.path.strip('/').lower()
    if not NAME.fullmatch(name):raise ValueError('Choose one Twitch channel.')
    return name

def parse_message(line, channel):
    tags={}
    if line.startswith('@'):
        raw,_,line=line.partition(' ')
        tags=dict(item.partition('=')[::2] for item in raw[1:].split(';'))
    match=re.fullmatch(r':([a-zA-Z0-9_]+)![^ ]+ PRIVMSG #([a-zA-Z0-9_]+) :(.*)',line)
    if not match or match[2].lower()!=channel:return None
    return {'id':tags.get('id') or hashlib.sha256(line.encode()).hexdigest(),
            'author':match[1][:80], 'text':match[3][:500], 'timestamp':int(time.time()*1000)}

class TwitchChat:
    def __init__(self):
        self.lock=threading.RLock();self.generation=0;self.socket=None
        self.messages=deque(maxlen=30);self.status='Disconnected';self.connected=False

    def stop(self):
        with self.lock:
            self.generation+=1;connection=self.socket;self.socket=None;self.connected=False;self.messages.clear();self.status='Disconnected'
        if connection:
            try:connection.close()
            except OSError:pass

    def connect(self,link,username='',token=''):
        from agent_connections import secret_get,secret_set
        if not isinstance(username,str) or not isinstance(token,str) or len(username)>25 or len(token)>206:raise ValueError('Use a Twitch username and OAuth token, not another input type.')
        channel=channel_name(link);saved=secret_get('twitch-chat')
        username=(username or saved.get('username','')).lower();token=(token or saved.get('token','')).removeprefix('oauth:')
        if not NAME.fullmatch(username) or not re.fullmatch('[A-Za-z0-9]{10,200}',token):raise ValueError('Enter the Twitch account username and its chat:read OAuth token. Do not use your password.')
        import requests
        try:
            result=requests.get('https://id.twitch.tv/oauth2/validate',headers={'Authorization':'OAuth '+token},timeout=10)
            data=result.json()
        except (requests.RequestException,ValueError):raise ValueError('Could not verify Twitch authorization. Retry when online.') from None
        if result.status_code!=200 or data.get('login','').lower()!=username or 'chat:read' not in data.get('scopes',[]):raise ValueError('Twitch authorization must match the username and include chat:read.')
        secret_set('twitch-chat',{'username':username,'token':token})
        self.stop()
        with self.lock:generation=self.generation;self.status='Connecting to Twitch…'
        threading.Thread(target=self._read,args=(channel,username,token,generation),daemon=True,name='SakuraTwitch').start()
        return channel

    def _read(self,channel,username,token,generation):
        connection=None
        try:
            connection=ssl.create_default_context().wrap_socket(socket.create_connection(('irc.chat.twitch.tv',6697),timeout=10),server_hostname='irc.chat.twitch.tv');connection.settimeout(1)
            with self.lock:
                if generation!=self.generation:return
                self.socket=connection
            connection.sendall(('PASS oauth:'+token+'\r\nNICK '+username+'\r\nCAP REQ :twitch.tv/tags twitch.tv/commands\r\nJOIN #'+channel+'\r\n').encode())
            pending=b'';seen=deque(maxlen=1000)
            while generation==self.generation:
                try:chunk=connection.recv(8192)
                except socket.timeout:continue
                if not chunk:raise ValueError('Twitch disconnected. Reconnect to resume chat.')
                pending+=chunk
                if len(pending)>32768:raise ValueError('Twitch returned an oversized message.')
                while b'\r\n' in pending:
                    raw,pending=pending.split(b'\r\n',1);line=raw.decode('utf-8','replace')
                    if line=='PING :tmi.twitch.tv':connection.sendall(b'PONG :tmi.twitch.tv\r\n');continue
                    if 'Login authentication failed' in line:raise ValueError('Twitch rejected the saved token. Sign in again.')
                    if ' 366 ' in line or (' JOIN #'+channel) in line:
                        with self.lock:
                            if generation==self.generation:self.connected=True;self.status='Connected to Twitch · '+channel
                    message=parse_message(line,channel)
                    if message and message['id'] not in seen:
                        seen.append(message['id'])
                        with self.lock:
                            if generation==self.generation:self.messages.append(message)
        except Exception:
            with self.lock:
                if generation==self.generation:self.connected=False;self.status='Twitch chat disconnected. Check the account token, network and channel, then reconnect.'
        finally:
            if connection:
                try:connection.close()
                except OSError:pass

    def poll(self):
        with self.lock:
            messages=list(self.messages);self.messages.clear()
            return {'connected':self.connected,'status':self.status,'messages':messages}

chat=TwitchChat()
