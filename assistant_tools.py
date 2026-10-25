"""Discoverable local tools and bounded, explicitly requested multi-step actions."""
import re
import threading
import time
import uuid
from collections import deque

_lock=threading.Lock()
_runs=deque(maxlen=20)
_workflow_lock=threading.Lock()
_CAPABILITIES=[
 {'id':'system.status','name':'PC status','examples':['PC status','CPU usage','RAM usage','battery level'],'permission':'computer_access','platform':'Windows measurements; basic disk information elsewhere'},
 {'id':'audio.volume','name':'System output volume','examples':['set volume to 30%','volume up','mute volume','unmute volume'],'permission':'computer_access','platform':'Windows'},
 {'id':'files.find','name':'Find files by name','examples':['find file report in downloads'],'permission':'computer_access','scope':'Top level of Downloads, Documents or Desktop; read-only; up to 20 matches'},
 {'id':'apps.open','name':'Launch an installed app or approved website','examples':['open YouTube','open calculator'],'permission':'computer_access'},
 {'id':'reminders','name':'Timers and alarms','examples':['start a timer for 2 minutes','cancel the timer'],'permission':'none'},
 {'id':'broadcast.effects','name':'NVIDIA Broadcast camera and microphone effects','examples':['blur my background','put studio voice on','turn off background blur'],'permission':'computer_access','scope':'Only the listed effects, and only through an NVIDIA Broadcast MCP connection you added yourself'},
 {'id':'workflow','name':'Explicit action sequence','examples':['open YouTube then set volume to 30%'],'scope':'At most five known steps, preflight permissions, stop on failure; no arbitrary code'},
]

def capabilities():return [dict(x) for x in _CAPABILITIES]
def runs():
    import copy
    with _lock:return copy.deepcopy(list(_runs))

def cancel_run(identifier=None):
    with _lock:
        for run in reversed(_runs):
            if run['status']=='running' and (identifier is None or run['id']==identifier):
                run['cancel_requested']=True
                return True
    return False

def classify(text):
    t=text.strip().lower().rstrip('.!?')
    if re.fullmatch(r'(?:show |check |tell me (?:the |my )?|what(?:\x27s| is) (?:the |my )?)?(?:pc status|system status|system information|cpu usage|gpu usage|vram usage|ram usage|memory usage|battery(?: level| status)?|disk space|free disk space)',t):return ('system.status',{})
    match=re.fullmatch(r'(?:set |change )?(?:the |system |computer )?volume(?: to)? (\d{1,3})(?:\s*(?:%|percent))?',t)
    if match:
        n=int(match[1])
        if n>100:raise ValueError('Choose a volume from 0 to 100 percent.')
        return ('audio.volume',{'action':'set','value':n})
    match=re.fullmatch(r'(?:turn (?:the )?)?(?:volume|sound) (up|down)|(?:(mute|unmute)(?: (?:the )?(?:volume|sound|speakers|computer))?)',t)
    if match:return ('audio.volume',{'action':match[1] or match[2]})
    if t in ('volume','volume level','current volume','what is the volume','what is my volume'):return ('audio.volume',{'action':'get'})
    match=re.fullmatch(r'(?:find|search for) (?:a |the )?file (.{1,100}?) in (?:my )?(downloads|documents|desktop)',text.strip(),re.I)
    if match:return ('files.find',{'query':match[1],'location':match[2].lower()})
    from broadcast_effects import classify as classify_effects
    effects=classify_effects(text)
    if effects:
        changes=effects.get('changes') or []
        if changes:return ('broadcast.effects',{'changes':changes})
        if effects.get('needs_asset'):return ('broadcast.effects',{'changes':[],'needs_asset':effects['needs_asset']})
    return None

def execute(action,arguments):
    from system_tools import system_status,status_reply,volume,find_files
    if action=='system.status':
        data=system_status();return {'ok':True,'reply':status_reply(data),'data':data}
    if action=='audio.volume':
        data=volume(**arguments);return {'ok':True,'reply':f"System volume is {data['percent']} percent"+(' and muted.' if data['muted'] else '.'),'data':data}
    if action=='files.find':
        data=find_files(**arguments)
        reply=('Found: '+', '.join(x['name'] for x in data['files'])+'.' if data['files'] else 'No matching files found in '+arguments['location']+'.')
        if data['limited']:reply+=' Results are limited; try a more specific file name.'
        return {'ok':True,'reply':reply,'data':data}
    if action=='broadcast.effects':
        from broadcast_effects import handle_request
        return handle_request(arguments)
    raise ValueError('Unsupported action.')

def _delegate_known(text):
    # Match the deterministic command vocabulary, never arbitrary LLM proposals.
    if re.fullmatch(r'(?:open|launch|start) [\w .+-]{1,100}',text,re.I) and not re.search(r'\b(?:timer|alarm)\b',text,re.I):return True
    if re.fullmatch(r'(?:set|start|make) (?:a |an )?(?:timer|alarm).{0,70}|(?:set|start|make) (?:a |an )?.{1,50} (?:timer|alarm)',text,re.I):return True
    return False

def handle_command(text,computer_access=False,assistant_name='Sakura'):
    if text in ('show task results','show recent action results','what happened to my task'):
        history=runs()
        if not history:return 'There are no action sequences in this app session.'
        current=history[-1]
        return current['status'].capitalize()+'. '+' '.join(step['reply'] for step in current['steps'])
    if text in ('stop current task','cancel current task','stop current sequence'):
        return 'Stopping before the next action.' if cancel_run() else 'There is no running action sequence.'
    if text in ('what actions can you do','show capabilities','list capabilities','show available actions','what can you do','what are your capabilities'):
        return 'I can check PC status, change system volume, find files by name, open apps and websites, manage timers and alarms, and switch NVIDIA Broadcast camera and microphone effects such as background blur or studio voice. Join up to five supported actions with “then”. PC, file and Broadcast actions need computer access enabled.'
    try:
        action=classify(text)
        if action:
            if not computer_access:return 'Enable computer access in Settings first to use PC tools.'
            result=execute(*action);return result['reply']
        pieces=re.split(r'\s*(?:,?\s+(?:and )?then\s+|;\s*)',text,flags=re.I)
        if len(pieces)<2:return None
        # Ignore ordinary conversation, rather than interpreting every "then" as a workflow.
        if not any(classify(x) or _delegate_known(x) for x in pieces):return None
        if len(pieces)>5:return 'Use at most five actions in one sequence.'
        plan=[]
        for piece in pieces:
            action=classify(piece)
            if not action and not _delegate_known(piece):return 'I cannot execute that whole sequence. Unsupported step: '+piece+'. No actions were started.'
            needs_access=action is not None or bool(re.match(r'(?:open|launch|start) ',piece,re.I) and not re.search(r'\b(?:timer|alarm)\b',piece,re.I))
            if needs_access and not computer_access:return 'Enable computer access first. No actions in the sequence were started.'
            plan.append((piece,action))
        if not _workflow_lock.acquire(blocking=False):return 'Another action sequence is running. Wait for it or say cancel current task.'
        run={'id':uuid.uuid4().hex,'created_at':time.time(),'status':'running','steps':[]}
        with _lock:_runs.append(run)
        for piece,action in plan:
            with _lock:
                if run.get('cancel_requested'):
                    run['status']='cancelled'
                    break
            try:
                if action:result=execute(*action)
                else:
                    from assistant_commands import run_command
                    reply=run_command(piece,computer_access,assistant_name)
                    failed=not reply or bool(re.search(r"couldn't|could not|not find|not found|enable |invalid|please choose|tell me a|what time|already passed|unavailable|no matching",reply,re.I))
                    result={'ok':not failed,'reply':reply or 'This action was not recognized.'}
                with _lock:run['steps'].append({'request':piece,**result})
                if not result['ok']:
                    with _lock:run['status']='failed'
                    break
            except Exception as error:
                with _lock:run['steps'].append({'request':piece,'ok':False,'reply':str(error)});run['status']='failed'
                break
        with _lock:
            if run['status']=='running':run['status']='completed'
            replies=[x['reply'] for x in run['steps']]
            stopped=run['status'] in ('failed','cancelled')
        _workflow_lock.release()
        return ' '.join(replies)+(' Remaining steps were not run.' if stopped else '')
    except (OSError,ValueError,RuntimeError) as error:return 'I could not complete that action: '+str(error)
