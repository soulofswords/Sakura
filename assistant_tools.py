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
 {'id':'system.status','name':'PC status','examples':['PC status','PC specs','can you see my pc specs','CPU usage','RAM usage','battery level'],'permission':'computer_access','platform':'Windows measurements; basic disk information elsewhere'},
 {'id':'audio.volume','name':'System output volume','examples':['set volume to 30%','volume up','mute volume','unmute volume'],'permission':'computer_access','platform':'Windows'},
 {'id':'display.brightness','name':'Primary display brightness','examples':['brightness','set brightness to 40%','brightness up'],'permission':'computer_access','platform':'Windows DDC/CI','scope':'Reads the primary monitor; a change follows the PC-action review setting in Theme → Computer access.'},
 {'id':'audio.voice','name':'My own speaking voice','examples':['switch to Bella','use the Nicole voice','talk like Puck','what voices do I have'],'permission':'none','scope':'Any installed Kokoro or Windows voice by name; ambiguous names are asked about instead of guessed'},
 {'id':'clipboard.read','name':'Read clipboard text','examples':['read clipboard','what is on the clipboard','paste clipboard'],'permission':'none','scope':'Reads the current Windows clipboard text. Never watches the clipboard continuously.'},
 {'id':'clipboard.write','name':'Write text to clipboard','examples':['copy hello world to clipboard','set clipboard to'],'permission':'none','scope':'Writes text to the Windows clipboard. Maximum 4096 characters.'},
 {'id':'clipboard.transform','name':'Transform clipboard text','examples':['make clipboard uppercase','clipboard to lowercase','trim clipboard','capitalize clipboard'],'permission':'none','scope':'Reads clipboard text, applies a simple text transform (uppercase, lowercase, title, sentence, trim), and writes it back.'},
 {'id':'clipboard.ai_transform','name':'AI transform clipboard text','examples':['ai transform clipboard','rewrite clipboard to be more professional','improve clipboard text','make clipboard text shorter'],'permission':'computer_access','scope':'Sends clipboard text to the selected AI model for rewriting, then writes the result back. Requires an AI model to be configured.'},
 {'id':'files.find','name':'Find files by name','examples':['find file report in downloads'],'permission':'computer_access','scope':'Top level of Downloads, Documents or Desktop; read-only; up to 20 matches'},
 {'id':'apps.open','name':'Launch an installed app or approved website','examples':['open YouTube','open calculator'],'permission':'computer_access'},
 {'id':'desktop.input','name':'Click, type, press keys and scroll on screen','examples':['click Save','click at 640, 360','type hello world','press ctrl s','scroll down'],'permission':'computer_access','scope':'One reviewed action at a time; clicks use words found by offline OCR or exact screen coordinates; at most 500 typed characters and four keys per shortcut'},
 {'id':'reminders','name':'Timers and alarms','examples':['start a timer for 2 minutes','cancel the timer'],'permission':'none'},
 {'id':'memory.browse','name':'Browse saved memory procedures','examples':['show learned procedures','browse memory','what did I learn'],'permission':'none','scope':'Lists saved agent learning entries from local memory with category, tools and success count.'},
 {'id':'process.list','name':'List running processes','examples':['list processes'],'permission':'computer_access','scope':'Returns a bounded PID/name/status list without command lines or environment data.'},
 {'id':'process.kill','name':'Kill a process','examples':['kill process 1234','terminate that task'],'permission':'computer_access','scope':'Kill a process by PID with approval. Never kills system processes.'},
 {'id':'files.pdf.create','name':'Create PDF document','examples':['create PDF report','write resume PDF'],'permission':'computer_access','scope':'Agent mode creates one reviewed PDF inside the selected workspace. New files only; no external PDF service.'},
 {'id':'expression.change','name':'Change avatar expression','examples':['show happy expression','switch to sad face','use the blush expression'],'permission':'none','scope':'Applies an existing expression in the currently loaded model; unavailable names are reported by the viewer.'},
 {'id':'memory.forget','name':'Forget one saved thing by topic','examples':['forget my birthday','forget that I like coffee'],'permission':'none','scope':'Only saved memory items and recent messages that mention the topic; a full reset stays on the Settings page'},
 {'id':'skills.execute','name':'Use a saved Agent skill','examples':['run skill brag','use my skill weekly-report'],'permission':'none','scope':'Select the skill in Agent mode with a workspace and planning AI. It guides real reviewed Agent steps; chat never pretends that printing its instructions executed it.'},
 {'id':'broadcast.effects','name':'NVIDIA Broadcast camera and microphone effects','examples':['blur my background','put studio voice on','turn off background blur'],'permission':'computer_access','scope':'Only the listed effects, and only through an NVIDIA Broadcast MCP connection you added yourself'},
 {'id':'workflow','name':'Explicit action sequence','examples':['open YouTube then set volume to 30%'],'scope':'At most five known steps, preflight permissions, stop on failure; no arbitrary code'},
]

def capabilities():return [dict(x) for x in _CAPABILITIES]
# Changing which voice Sakura speaks with, forgetting one saved fact, and plain text
# clipboard reads/writes are her own settings, not PC actions. The AI clipboard rewrite
# still needs computer access because it sends the text to a model.
_NO_PERMISSION={'audio.voice','audio.voices','memory.forget',
                'clipboard.read','clipboard.write','clipboard.transform',
                'expression.change','skills.execute','memory.browse'}
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

def device_mention(text):
    """Which PC setting this sentence is about, so a later "make it 50" has a target."""
    value=str(text or '')
    if re.search(r'\b(?:volume|sound|audio|speakers?|mute|muted|unmute)\b',value,re.I):return 'volume'
    if re.search(r'\bbrightness\b|\b(?:screen|display|monitor)\b[^.!?\n]{0,20}\b(?:brighter|dimmer|darker|bright)\b',value,re.I):return 'brightness'
    return None

def device_followup(text, device, assistant_name='Sakura'):
    """Rewrite "make it 50 percent" into an explicit command for the setting just discussed."""
    if device not in ('volume','brightness'):return None
    from assistant_commands import normalize
    value=normalize(str(text or ''),assistant_name)
    match=re.fullmatch(r'(?:set|change|make|turn|put|adjust|bring|increase|raise|decrease|lower|reduce|drop|bump|boost)\s+(?:it|that)(?:\s+(?:up|down))?(?:\s+(?:to|at))?\s+(\d{1,3})(?:\s*(?:%|percent))?(?:\s+(?:now|right now|directly|please|for me))*',value,re.I)
    if match:
        number=int(match[1])
        if number>100:raise ValueError(f'Choose a {device} from 0 to 100 percent.')
        return f'set {device} to {number}'
    # "Decrease it." names a direction, not a level; it still targets the setting in focus.
    # The pronoun is required, so a bare "decrease" keeps going through the normal grammar.
    if re.fullmatch(r'(?:decrease|lower|reduce|drop|quieter)\s+(?:it|that)(?:\s+down)?',value,re.I):return f'{device} down'
    if re.fullmatch(r'(?:increase|raise|boost|bump|louder)\s+(?:it|that)(?:\s+up)?',value,re.I):return f'{device} up'
    return None


class DeviceContext:
    """Short-lived conversation targets; no device writes happen here."""
    def __init__(self, ttl=120, clock=time.monotonic):
        self.ttl=ttl;self.clock=clock;self.targets={};self.lock=threading.Lock()

    def _clauses(self, value):
        """The whole turn first, then only its last sentence: "It is 50%. Decrease it." is one intent."""
        parts=[part.strip() for part in re.split(r'[.!?]+',value) if part.strip()]
        return [value] if len(parts)<2 else [value,parts[-1]]

    def _match(self, value, target, assistant_name):
        """What this turn wants: a level, an unresolvable pronoun, or a new setting request."""
        probe=device_followup(value,target[0] if target else 'volume',assistant_name)
        if probe is not None:
            return ('ask',None,None) if target is None else ('set',probe,target[0])
        if target is not None:
            # A spoken level with no device word only means something while a setting is in focus.
            bare=re.fullmatch(r'(\d{1,3})\s*(?:%|percent)?',value,re.I)
            if bare:
                number=int(bare[1])
                if number>100:raise ValueError(f'Choose a {target[0]} from 0 to 100 percent.')
                return ('set',f'set {target[0]} to {number}',target[0])
        action=classify(value)
        if action and action[0]=='audio.volume':return ('focus',None,'volume')
        if action and action[0]=='display.brightness':return ('focus',None,'brightness')
        return None

    def resolve(self, text, channel, assistant_name='Sakura'):
        if channel not in ('desktop','phone','ai-vtuber'):
            raise ValueError('Unsupported device conversation channel.')
        from assistant_commands import normalize
        normalized=normalize(text,assistant_name)
        with self.lock:
            now=self.clock()
            self.targets={key:value for key,value in self.targets.items() if 0<=now-value[1]<self.ttl}
            # Resolve pronouns before other tool grammars inspect percentages.
            target=self.targets.get(channel)
            for clause in self._clauses(normalized):
                outcome=self._match(clause,target,assistant_name)
                if outcome is None:continue
                kind,value,device=outcome
                if kind=='ask':
                    raise ValueError('Do you mean system volume or display brightness? Please name the setting; nothing was changed.')
                # Only actual setting requests hold the target; incidental words like
                # "audio in this movie" must not turn the next number into a write.
                self.targets[channel]=(device,now)
                if kind=='set':return value
                return clause if clause!=text else None
            # A change of subject ends pronoun context rather than attaching a
            # later unrelated "make it 50" to an old request. A one or two word
            # fragment ("decrase") is misheard speech, not a new topic, so the
            # target survives it and still expires on its own clock.
            if target is not None and len(normalized.split())<=2 and not classify(normalized):
                self.targets[channel]=(target[0],now)
                return None
            self.targets.pop(channel,None)
            return None

def classify(text):
    t=text.strip().lower().rstrip('.!?').strip()
    from desktop_control import parse_command, parse_media
    # Media keys come first so "press playpause" routes to media.press, not desktop.press.
    media=parse_media(text)
    if media:return ('media.press',{'key':media})
    desktop=parse_command(text)
    if desktop:return (desktop['action'],desktop['arguments'])
    if re.fullmatch(r"(?:show |check |tell me |can (?:you|u) (?:see|show|tell me) |do (?:you|u) (?:know|have) |what(?:\x27?s| is| are) )?(?:the |my |your |this )?(?:pc status|system status|system information|cpu usage|gpu usage|vram usage|ram usage|memory usage|battery(?: level| status)?|disk space|free disk space|(?:(?:pc|computer|system|hardware|machine) )?spec(?:s|ifications)?|processor|cpu(?: model| name)?|graphics card|gpu name|windows version|os version|hardware)",t):return ('system.status',{})
    match=re.fullmatch(r'(?:set |change )?(?:the |system |computer )?volume(?: to)? (\d{1,3})(?:\s*(?:%|percent))?',t)
    if match:
        n=int(match[1])
        if n>100:raise ValueError('Choose a volume from 0 to 100 percent.')
        return ('audio.volume',{'action':'set','value':n})
    match=re.fullmatch(r'(?:set|change|make|turn|put|adjust|bring|increase|raise|decrease|lower|reduce|drop|bump|boost)\s+(?:the\s+|my\s+|system\s+|computer\s+)?(?:volume|sound|audio)\s+(?:up\s+|down\s+)?(?:(?:to|at)\s+)?(\d{1,3})(?:\s*(?:%|percent))?',t)
    if match:
        n=int(match[1])
        if n>100:raise ValueError('Choose a volume from 0 to 100 percent.')
        return ('audio.volume',{'action':'set','value':n})
    match=re.fullmatch(r'(?:turn (?:the )?)?(?:volume|sound) (up|down)|(?:(mute|unmute)(?: (?:the )?(?:volume|sound|speakers|computer))?)',t)
    if match:return ('audio.volume',{'action':match[1] or match[2]})
    # People say "increase volume" or "turn it down", not "press volumeup".
    spoken=re.sub(r'\b(?:please|just|a bit|a little|slightly|a touch)\b',' ',t)
    spoken=re.sub(r'\s+',' ',spoken).strip()
    if re.fullmatch(r'(?:increase|raise|boost|bump up|louder|turn (?:it|that|the volume|the sound) up|turn up|make it louder)(?: (?:the |my |your |this )?(?:volume|sound))?',spoken):return ('audio.volume',{'action':'up'})
    if re.fullmatch(r'(?:decrease|lower|reduce|drop|quieter|turn (?:it|that|the volume|the sound) down|turn down|make it quieter)(?: (?:the |my |your |this )?(?:volume|sound))?',spoken):return ('audio.volume',{'action':'down'})
    if t in ('volume','volume level','current volume','what is the volume','what is my volume'):return ('audio.volume',{'action':'get'})
    match=re.fullmatch(r'(?:set |change )?(?:the |my |display |screen |monitor )?brightness(?: to)? (\d{1,3})(?:\s*(?:%|percent))?',t)
    if match:
        value=int(match[1])
        if value>100:raise ValueError('Choose brightness from 0 to 100 percent.')
        return ('display.brightness',{'action':'set','value':value})
    match=re.fullmatch(r'(?:set|change|make|turn|put|adjust|bring|increase|raise|decrease|lower|reduce|drop|bump|boost)\s+(?:the\s+|my\s+|display\s+|screen\s+|monitor\s+)?brightness\s+(?:up\s+|down\s+)?(?:(?:to|at)\s+)?(\d{1,3})(?:\s*(?:%|percent))?',t)
    if match:
        value=int(match[1])
        if value>100:raise ValueError('Choose brightness from 0 to 100 percent.')
        return ('display.brightness',{'action':'set','value':value})
    match=re.fullmatch(r'(?:(?:turn|move) )?(?:the |my |display |screen |monitor )?brightness (up|down)',t)
    if match:return ('display.brightness',{'action':match.group(1)})
    if t in ('brightness','brightness level','current brightness','what is the brightness','what is my brightness'):
        return ('display.brightness',{'action':'get'})
    from spoken_voice import request as voice_request
    wanted=voice_request(t)
    if wanted:
        if wanted.get('show'):return ('audio.voices',{})
        return ('audio.voice',{'label':wanted['label']})
    match=re.fullmatch(r'(?:find|search for) (?:a |the )?file (.{1,100}?) in (?:my )?(downloads|documents|desktop)',text.strip(),re.I)
    if match:return ('files.find',{'query':match[1],'location':match[2].lower()})
    # Clipboard commands — voice-reachable, never watches the clipboard continuously.
    # Matched against the original wording so the copied text keeps its capitalisation,
    # and the text itself is captured non-greedily so words like "to" or "the" that
    # belong to the command never land inside the copied string.
    raw=text.strip().rstrip('.!?').strip()
    match=re.fullmatch(r'(?:read|show|paste|get)\s+(?:(?:what(?:\x27s| is)\s+)?(?:on|in)\s+)?(?:my\s+|the\s+)?clipboard|what\s+(?:is|was)\s+(?:currently\s+)?(?:on|in)\s+(?:my\s+|the\s+)?clipboard',raw,re.I)
    if match:return ('clipboard.read',{})
    match=re.fullmatch(r'(?:copy|set|put|write)\s+(.{1,4096}?)\s+(?:to\s+)?(?:the\s+)?clipboard',raw,re.I)
    if match:
        # Strip any trailing connector words that belong to command, not content
        captured=match.group(1).strip()
        # If captured ends with connector words that should belong to command, trim
        for connector in (' to', ' the', ' on', ' of', ' is', ' are'):
            if captured.lower().endswith(connector):
                captured=captured[:-len(connector)].rstrip()
        if captured and len(captured)<=4096 and not re.fullmatch(r'(?:to|the|on|of|is|are)\s*', captured,re.I):
            return ('clipboard.write',{'text':captured})
    match=re.fullmatch(r'(?:copy|set|put|write)\s+(?:the\s+)?clipboard\s+(?:to\s+)?(.{1,4096})',raw,re.I)
    if match:return ('clipboard.write',{'text':match.group(1)})
    match=re.fullmatch(r'(?:clipboard\s+to\s+|make\s+clipboard\s+|transform\s+clipboard\s+)(uppercase|upper|lowercase|lower|title|titlecase|sentence|sentencecase|trim|strip)',t)
    if match:return ('clipboard.transform',{'transform':match.group(1)})
    match=re.fullmatch(r'(uppercase|upper|lowercase|lower|title|titlecase|sentence|sentencecase|trim|strip)\s+(?:the\s+)?clipboard',t)
    if match:return ('clipboard.transform',{'transform':match.group(1)})
    # AI transform — sends clipboard text to the selected model for rewriting.
    match=re.fullmatch(r'(?:ai|artificial intelligence)\s+(?:transform|rewrite|improve|fix|enhance)\s+(?:the\s+)?clipboard(?:\s+(.{1,200}))?',t)
    if match:return ('clipboard.ai_transform',{'instruction':match.group(1) or 'improve the text'})
    match=re.fullmatch(r'(?:rewrite|improve|fix|enhance)\s+(?:the\s+)?clipboard(?:\s+(.{1,200}))?',t)
    if match:return ('clipboard.ai_transform',{'instruction':match.group(1) or 'improve the text'})
    from broadcast_effects import classify as classify_effects
    effects=classify_effects(text)
    if effects:
        changes=effects.get('changes') or []
        if changes:return ('broadcast.effects',{'changes':changes})
        if effects.get('needs_asset'):return ('broadcast.effects',{'changes':[],'needs_asset':effects['needs_asset']})
    match=re.fullmatch(r'(?:forget|delete|erase|remove)\s+((?:(?:that|about|the|your|my|our|you remember(?:ed)?|what you (?:know|remember)(?: about)?)\s+)*.{1,80})',t)
    if match:
        topic=match.group(1).strip()
        # Broadcast effects and reminders own their own removal words; this one is only about saved memory.
        if not re.search(r'\b(?:timers?|alarms?|reminders?|blur|background|noise|echo|cameras?|microphones?|voices?|volume|apps?|windows?|files?|devices?|phones?|history|chats?|conversations?|messages?|settings?)\b',topic):
            return ('memory.forget',{'topic':topic})
    # Browse saved memory procedures
    if match:=re.fullmatch(r'(?:list|show|browse)\s+(?:the\s+)?(?:running\s+)?process(?:es)?',t):
        return ('process.list',{})
    if match:=re.fullmatch(r'(?:kill|terminate|stop)\s+(?:process\s+)?(\d+)',t):
        return ('process.kill',{'pid':int(match.group(1))})
    if match:=re.fullmatch(r'(?:run|execute|use)\s+(?:my\s+)?skill\s+/?([a-z0-9][a-z0-9-]{0,59})',t):
        return ('skills.execute',{'name':match.group(1).strip()})
    from avatar_expression_command import request as expression_request
    expression=expression_request(text)
    if expression:return ('expression.change',expression)
    match=re.fullmatch(r'(?:show|list|browse|what)\s+(?:my\s+)?(?:saved\s+)?(?:learning|memory|procedures)|list\s+(?:my\s+)?(?:learning|memory)',t)
    if match:return ('memory.browse',{})
    return None

def execute(action,arguments,bindings=None):
    if action.startswith('desktop.'):
        from desktop_control import execute_action
        return execute_action(action,arguments)
    from system_tools import system_status,status_reply,volume,find_files
    if action=='system.status':
        data=system_status();return {'ok':True,'reply':status_reply(data),'data':data}
    if action=='audio.volume':
        data=volume(**arguments);return {'ok':True,'reply':f"System volume is {data['percent']} percent"+(' and muted.' if data['muted'] else '.'),'data':data}
    if action=='display.brightness':
        from brightness_control import brightness
        data=brightness(arguments.get('action','get'),arguments.get('value'))
        return {'ok':True,'reply':f"Primary display brightness is {data['current']} percent.",'data':data}
    if action=='audio.voices':
        from spoken_voice import summary, windows_voices
        return {'ok':True,'reply':summary(windows_voices()),'data':{}}
    if action=='audio.voice':
        from spoken_voice import resolve
        # Resolving against the real catalogue is what makes “switch to Bella” land on Bella.
        chosen=resolve(arguments['label'])
        from app import switch_voice
        return switch_voice(chosen['id'])
    if action=='files.find':
        data=find_files(**arguments)
        reply=('Found: '+', '.join(x['name'] for x in data['files'])+'.' if data['files'] else 'No matching files found in '+arguments['location']+'.')
        if data['limited']:reply+=' Results are limited; try a more specific file name.'
        return {'ok':True,'reply':reply,'data':data}
    if action=='clipboard.read':
        from native_clipboard import read_text
        text=read_text()
        return {'ok':True,'reply':text if text else 'Clipboard is empty.','data':{'text':text}}
    if action=='clipboard.write':
        from native_clipboard import copy_text
        result=copy_text(arguments['text'])
        return {'ok':True,'reply':'Copied to clipboard.','data':result}
    if action=='clipboard.transform':
        from native_clipboard import read_text, copy_text
        transform=str(arguments.get('transform','')).lower()
        text=read_text()
        if not text:
            return {'ok':False,'reply':'Clipboard is empty; nothing to transform.','data':{}}
        if transform in ('uppercase','upper'):
            result=text.upper()
        elif transform in ('lowercase','lower'):
            result=text.lower()
        elif transform in ('title','titlecase'):
            result=text.title()
        elif transform in ('sentence','sentencecase'):
            result=text[:1].upper()+text[1:].lower() if text else text
        elif transform in ('trim','strip'):
            result=text.strip()
        else:
            return {'ok':False,'reply':'Unknown transform. Use uppercase, lowercase, title, sentence, or trim.','data':{}}
        copy_text(result)
        return {'ok':True,'reply':f'Clipboard transformed to {transform}.','data':{'result':result}}
    if action=='clipboard.ai_transform':
        from native_clipboard import read_text, copy_text
        instruction=str(arguments.get('instruction','improve the text')).strip()
        if not instruction:
            instruction='improve the text'
        text=read_text()
        if not text:
            return {'ok':False,'reply':'Clipboard is empty; nothing to transform.','data':{}}
        # Limit clipboard content sent to the model.
        if len(text)>4000:
            return {'ok':False,'reply':'Clipboard text is too long for AI transform (max 4000 characters).','data':{}}
        try:
            from app import llm
            if llm is None:
                return {'ok':False,'reply':'No AI model is configured. Load a model in Local AI or configure a cloud provider first.','data':{}}
            messages=[
                {'role':'system','content':'You transform text exactly as instructed. Return only the transformed text, with no explanations, no preamble, and no quotation marks around the result. Do not add "Here is the transformed text:" or similar. Just output the result.'},
                {'role':'user','content':f'Transformation instruction: {instruction}\n\nText to transform:\n{text}'}
            ]
            result=llm._request_raw(messages)
            if not result or not result.strip():
                return {'ok':False,'reply':'The AI model returned an empty response.','data':{}}
            copy_text(result.strip())
            return {'ok':True,'reply':f'Clipboard AI-transformed ({instruction}).','data':{'result':result.strip()}}
        except ImportError:
            return {'ok':False,'reply':'AI model is not available.','data':{}}
        except Exception as error:
            return {'ok':False,'reply':'AI transform failed: '+str(error)[:500],'data':{}}
    if action=='media.press':
        from desktop_control import media_press
        media_press(arguments['key'])
        return {'ok':True,'reply':f'Pressed {arguments["key"]}.','data':{'key':arguments['key']}}
    if action=='expression.change':
        # Only reachable as one step of a multi-sentence sequence now: the chat route reads the
        # grammar from the whole sentence and hands the expression to the viewer itself.
        return {'ok':False,'reply':'I can change my expression only from a sentence of its own, not as one step in a sequence. Ask me the expression by itself.','data':{}}
    if action=='broadcast.effects':
        from broadcast_effects import handle_request
        return handle_request(arguments)
    if action=='memory.forget':
        from app import forget_about
        return forget_about(arguments['topic'])
    if action=='process.list':
        try:
            from process_tools import list_processes
            data=list_processes()
            shown=data['processes'][:20]
            reply=('Running processes: '+', '.join(f"{item['name']} ({item['pid']})" for item in shown)+'.') if shown else 'No visible processes were found.'
            if data['limited'] or len(data['processes'])>len(shown):reply+=' Open Agent mode for the bounded full list.'
            return {'ok': True, 'reply': reply, 'data': data}
        except Exception as error:
            return {'ok': False, 'reply': 'Process list failed: ' + str(error)[:500], 'data': {}}
    if action=='process.kill':
        try:
            from process_tools import terminate
            expected=(bindings or {}).get('processes',{}).get(str(arguments.get('pid')))
            data=terminate(arguments.get('pid'),expected)
            return {'ok':data['ok'],'reply':data['message'],'data':data}
        except Exception as error:
            return {'ok': False, 'reply': 'Kill failed (check PID): ' + str(error)[:500], 'data': {}}
    if action=='skills.execute':
        name=str(arguments.get('name','')).strip()
        if not name: return {'ok':False,'reply':'Which saved skill? Try "run skill learn" or list skills first.', 'data':{}}
        from agent_skills import AgentSkills
        from config import BASE_DIR
        try:
            skills_path = BASE_DIR / 'desktop-profile' / 'agent-skills.json'
            skills = AgentSkills(skills_path)
            skills.get(name)
            return {'ok':False,'reply':f'Skill “{name}” is saved. Open Agent mode, choose a workspace and planning AI, select that skill, then start the task. No procedure was executed from chat.', 'data':{'name':name,'source':'user-skill'}}
        except ValueError:
            return {'ok':False,'reply':'That skill is not in your library. Use Skills > List to see saved procedures.', 'data':{}}
        except Exception as error:
            return {'ok':False,'reply':'Could not read skill: '+str(error)[:500], 'data':{}}
    if action=='memory.browse':
        from agent_learning import AgentLearning
        from config import BASE_DIR
        path = BASE_DIR / 'desktop-profile' / 'agent-learning.json'
        try:
            learning = AgentLearning(path)
            status = learning.status()
            rows = status.get('procedures', [])
            shown = []
            for row in rows[:10]:
                shown.append({'category': row.get('category'), 'tools': row.get('tools'), 'successes': row.get('successes'), 'updated_at': row.get('updated_at')})
            return {'ok': True, 'reply': f"Saved procedures: {len(rows)} (showing first 10)." if rows else 'No saved learning procedures.', 'data': {'count': len(rows), 'shown': shown}}
        except Exception as error:
            return {'ok': False, 'reply': 'Memory browse failed: ' + str(error)[:500], 'data': {}}
    raise ValueError('Unsupported action.')

def _execute_reviewed(action, bindings):
    """Keep normal command calls unchanged; attach identity only where one was approved."""
    if bindings and bindings.get('processes'):
        return execute(*action,bindings=bindings)
    return execute(*action)

def _delegate_known(text):
    # Match the deterministic command vocabulary, never arbitrary LLM proposals.
    if re.fullmatch(r'(?:open|launch|start|run) [\w .+-]{1,100}',text,re.I) and not re.search(r'\b(?:timer|alarm)\b',text,re.I):return True
    if re.fullmatch(r'use (?:the )?(?:calculator|notepad|paint|chrome|edge)',text,re.I):return True
    if re.fullmatch(r'(?:set|start|make) (?:a |an )?(?:timer|alarm).{0,70}|(?:set|start|make) (?:a |an )?.{1,50} (?:timer|alarm)',text,re.I):return True
    return False

def _parse_sequence(text,computer_access):
    pieces=re.split(r'\s*(?:,?\s+(?:and )?then\s+|;\s*)',text,flags=re.I)
    if len(pieces)<2:return None,None
    # Ignore ordinary conversation, rather than interpreting every "then" as a workflow.
    if not any(classify(x) or _delegate_known(x) for x in pieces):return None,None
    if len(pieces)>5:return None,'Use at most five actions in one sequence.'
    plan=[]
    for piece in pieces:
        action=classify(piece)
        # Forgetting a saved fact is a single reply, never a step in a PC action sequence.
        if action and action[0]=='memory.forget':action=None
        if not action and not _delegate_known(piece):return None,'I cannot execute that whole sequence. Unsupported step: '+piece+'. No actions were started.'
        needs_access=action is not None or bool(re.match(r'(?:open|launch|start|run|use) ',piece,re.I) and not re.search(r'\b(?:timer|alarm)\b',piece,re.I))
        if needs_access and not computer_access:return None,'Enable computer access first. No actions in the sequence were started.'
        plan.append((piece,action))
    return plan,None

def _run_plan(run,plan,computer_access,assistant_name,channel='desktop',bindings=None):
    try:
        for piece,action in plan:
            with _lock:
                if run.get('cancel_requested'):
                    run['status']='cancelled'
                    break
            try:
                if action:result=_execute_reviewed(action,bindings)
                else:
                    from assistant_commands import run_command
                    reply=run_command(piece,computer_access,assistant_name,channel=channel)
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
        return ' '.join(replies)+(' Remaining steps were not run.' if stopped else '')
    finally:
        _workflow_lock.release()

def start_sequence(text,computer_access=False,assistant_name='Sakura',channel='desktop',bindings=None):
    """Run an explicit multi-step sequence on a worker thread. None when the text is not one."""
    plan,error=_parse_sequence(text,computer_access)
    if error:return {'error':error}
    if plan is None:return None
    if not _workflow_lock.acquire(blocking=False):
        return {'error':'Another action sequence is running. Wait for it or say cancel current task.'}
    run={'id':uuid.uuid4().hex,'created_at':time.time(),'status':'running','steps':[]}
    with _lock:_runs.append(run)
    try:
        threading.Thread(target=_run_plan,args=(run,plan,computer_access,assistant_name,channel,bindings),daemon=True,name='sakura-workflow').start()
    except RuntimeError:
        _workflow_lock.release()
        return {'error':'I could not start that action sequence.'}
    # Speak before the work, not after it: the steps report themselves as they land.
    return {'id':run['id'],'steps':len(plan),'ack':'Okay, starting that now.'}

def run_state(identifier):
    import copy
    with _lock:
        for run in reversed(_runs):
            if run['id']==identifier:return copy.deepcopy(run)
    return None

def handle_command(text,computer_access=False,assistant_name='Sakura',channel='desktop',bindings=None):
    if text in ('show task results','show recent action results','what happened to my task'):
        history=runs()
        if not history:return 'There are no action sequences in this app session.'
        current=history[-1]
        return current['status'].capitalize()+'. '+' '.join(step['reply'] for step in current['steps'])
    if text in ('stop current task','cancel current task','stop current sequence'):
        return 'Stopping before the next action.' if cancel_run() else 'There is no running action sequence.'
    if text in ('what actions can you do','show capabilities','list capabilities','show available actions','what can you do','what are your capabilities'):
        return 'I can check PC status, change system volume, find files by name, open apps and websites, click and type on screen, press keyboard shortcuts, scroll, manage timers and alarms, switch my own speaking voice by name, and switch NVIDIA Broadcast camera and microphone effects such as background blur or studio voice. Join up to five supported actions with “then”. PC, file, desktop-input and Broadcast actions need computer access enabled, and screen clicks, typing and shortcuts are reviewed before they run.'
    try:
        action=classify(text)
        if action:
            if not computer_access and action[0] not in _NO_PERMISSION:return 'Enable computer access in Settings first to use PC tools.'
            result=_execute_reviewed(action,bindings);return result['reply']
        plan,error=_parse_sequence(text,computer_access)
        if error:return error
        if plan is None:return None
        if not _workflow_lock.acquire(blocking=False):return 'Another action sequence is running. Wait for it or say cancel current task.'
        run={'id':uuid.uuid4().hex,'created_at':time.time(),'status':'running','steps':[]}
        with _lock:_runs.append(run)
        return _run_plan(run,plan,computer_access,assistant_name,channel,bindings)
    except (OSError,ValueError,RuntimeError) as error:return 'I could not complete that action: '+str(error)
