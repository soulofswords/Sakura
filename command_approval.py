"""Single-use, short-lived approvals for exact Companion PC commands."""
import re,secrets,threading,time
_pending={}
_lock=threading.Lock()
def required(text):
    pieces=re.split(r'\s*(?:,?\s+(?:and )?then\s+|;\s*)',text,flags=re.I)
    if len(pieces)>1:return bool(re.search(r'\bthen\b',text,re.I)) or any(required(piece) for piece in pieces)
    from assistant_tools import classify
    try:action=classify(text)
    except ValueError:return False
    if action and (action[0]=='broadcast.effects' or (action[0]=='audio.volume' and action[1].get('action')!='get')):return True
    return bool(re.search(r"\b(?:open|launch|start|search|google|then)\b",text,re.I))
def propose(text,channel):
    with _lock:
        now=time.monotonic()
        for key,value in list(_pending.items()):
            if value[2]<now:_pending.pop(key,None)
        if len(_pending)>=32:_pending.pop(next(iter(_pending)))
        identifier=secrets.token_urlsafe(24);_pending[identifier]=(text,channel,now+120)
        return identifier
def consume(identifier,approved):
    with _lock:value=_pending.pop(str(identifier),None)
    if not value or value[2]<time.monotonic():raise ValueError('This action expired. Ask again to review it.')
    return value[:2] if approved is True else None
