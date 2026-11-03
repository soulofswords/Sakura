"""Bounded single or simultaneous YouTube/Twitch inbox; credentials stay PC-local."""
import threading
from urllib.parse import urlsplit
import youtube_chat
import twitch_chat

class LiveChat:
    def __init__(self):self.sources={};self.lock=threading.RLock()
    def connect(self,link,username='',token='',service=None,twitch_link=''):
        if not isinstance(link,str) or len(link)>2048 or not isinstance(twitch_link,str) or len(twitch_link)>2048:
            raise ValueError('Enter valid livestream links under 2048 characters.')
        service=service or ('twitch' if urlsplit(link).hostname in ('twitch.tv','www.twitch.tv') else 'youtube')
        if service not in ('youtube','twitch','both'):raise ValueError('Choose YouTube, Twitch or YouTube + Twitch.')
        # Validate both addresses before starting either reader or changing the session.
        if service in ('youtube','both'):youtube_chat.video_id(link)
        if service in ('twitch','both'):twitch_chat.channel_name(twitch_link if service=='both' else link)
        with self.lock:
            self.stop()
            identities={}
            try:
                if service in ('youtube','both'):
                    identities['youtube']=youtube_chat.chat.connect(link);self.sources['youtube']=youtube_chat.chat
                if service in ('twitch','both'):
                    identities['twitch']=twitch_chat.chat.connect(twitch_link if service=='both' else link,username,token);self.sources['twitch']=twitch_chat.chat
            except Exception:
                self.stop();raise
            return identities if service=='both' else next(iter(identities.values()))
    def stop(self):
        with self.lock:
            youtube_chat.chat.stop();twitch_chat.chat.stop();self.sources={}
    def poll(self):
        with self.lock:
            states={name:source.poll() for name,source in self.sources.items()}
            messages=[]
            for name,state in states.items():
                for message in state.get('messages',[])[:30]:
                    messages.append({**message,'id':name+':'+str(message.get('id','')),'source':name})
            messages.sort(key=lambda message:message.get('timestamp',0))
            return {'connected':any(state.get('connected') for state in states.values()),
                    'all_connected':bool(states) and all(state.get('connected') for state in states.values()),
                    'services':{name:{'connected':bool(state.get('connected')),'status':state.get('status','')} for name,state in states.items()},
                    'status':' · '.join(name.title()+': '+str(state.get('status','')) for name,state in states.items()) or 'Disconnected',
                    'messages':messages[-60:]}
chat=LiveChat()
