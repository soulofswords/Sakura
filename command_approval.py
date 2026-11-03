"""Single-use, short-lived approvals for exact Companion PC commands."""
import re,secrets,threading,time
_pending={}
_lock=threading.Lock()
def _needs_review(text):
    pieces=re.split(r'\s*(?:,?\s+(?:and )?then\s+|;\s*)',text,flags=re.I)
    if len(pieces)>1:return bool(re.search(r'\bthen\b',text,re.I)) or any(_needs_review(piece) for piece in pieces)
    from assistant_tools import classify
    try:action=classify(text)
    except ValueError:return False
    if not action:
        # run_command classifies the speech-normalised form ("can you set it to 50"),
        # so the review gate must read that same form or a write slips through unreviewed.
        from assistant_commands import normalize
        try:action=classify(normalize(text))
        except ValueError:return False
    if action and (action[0].startswith('desktop.') or action[0]=='broadcast.effects'
            or action[0]=='process.kill'
            or (action[0].startswith('clipboard.') and action[0] != 'clipboard.read')
            or action[0].startswith('media.')
            or (action[0] in ('audio.volume','display.brightness') and action[1].get('action')!='get')):return True
    return bool(re.search(r"\b(?:open|launch|start|run|search|google|then)\b",text,re.I)
                or re.search(r"\buse (?:the )?(?:calculator|notepad|paint|chrome|edge)\b",text,re.I))
def _always_reviewed(text):
    """True when this action must keep its review card even with direct execution turned on.

    desktop.* types, clicks and scrolls into whichever window the user happens to have focused,
    and process.kill ends a task named by speech, so a mishearing is not recoverable by the user.
    """
    pieces=re.split(r'\s*(?:,?\s+(?:and )?then\s+|;\s*)',text,flags=re.I)
    if len(pieces)>1:return any(_always_reviewed(piece) for piece in pieces)
    from assistant_tools import classify
    from assistant_commands import normalize
    try:action=classify(text)
    except ValueError:return False
    if not action:
        try:action=classify(normalize(text))
        except ValueError:return False
    return bool(action) and (action[0].startswith('desktop.') or action[0]=='process.kill')
def required(text,settings=None):
    """Whether a PC action still has to be approved before it runs.

    Settings stored without the key keep the old review behaviour; the app saves it explicitly.
    """
    if not _needs_review(text):return False
    if isinstance(settings,dict) and settings.get('pc_action_review_required',True) is False:
        return _always_reviewed(text)
    return True
def _bindings_for(text):
    """Capture identities that must still match when a reviewed command runs."""
    from assistant_tools import classify
    from assistant_commands import normalize
    from process_tools import inspect_target
    bindings={'processes':{}}
    pieces=re.split(r'\s*(?:,?\s+(?:and )?then\s+|;\s*)',text,flags=re.I)
    for piece in pieces:
        try: action=classify(piece) or classify(normalize(piece))
        except ValueError: action=None
        if action and action[0]=='process.kill':
            identity=inspect_target(action[1].get('pid'))
            bindings['processes'][str(identity['pid'])]=identity
    return bindings

def propose(text,channel):
    from desktop_control import mark_target
    mark_target(text)
    bindings=_bindings_for(text)
    with _lock:
        now=time.monotonic()
        for key,value in list(_pending.items()):
            if value[2]<now:_pending.pop(key,None)
        if len(_pending)>=32:_pending.pop(next(iter(_pending)))
        identifier=secrets.token_urlsafe(24);_pending[identifier]=(text,channel,now+120,bindings)
        return identifier
def consume(identifier,approved):
    with _lock:value=_pending.pop(str(identifier),None)
    if not value or value[2]<time.monotonic():raise ValueError('This action expired. Ask again to review it.')
    return (value[0],value[1],value[3]) if approved is True else None
