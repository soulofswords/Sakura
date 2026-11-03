"""Local, persistent timers and alarms; no AI or cloud scheduler required."""
import json
import re
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


class Reminders:
    def __init__(self, path, clock=time.time):
        self.path=Path(path);self.clock=clock;self.lock=threading.RLock()

    def _load(self):
        if not self.path.exists():return []
        entries=json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(entries,list):raise ValueError('Invalid reminder file')
        return entries

    def _save(self, entries):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(self.path)

    def list(self):
        with self.lock:
            entries=self._load();changed=False
            for item in entries:
                if item['status']=='scheduled' and item['due']<=self.clock():item['status']='ringing';changed=True
            if changed:self._save(entries)
            return [dict(item,remaining=max(0,round(item['due']-self.clock()))) for item in entries]

    def add(self,kind,due,label):
        with self.lock:
            entries=self._load()
            if len(entries)>=100:raise ValueError('You already have 100 timers/alarms. Cancel some first.')
            item={'id':uuid.uuid4().hex[:8],'kind':kind,'due':due,'label':label[:100],'status':'scheduled','created':self.clock()}
            entries.append(item);self._save(entries);return item

    def dismiss(self,identifier, snooze=False):
        with self.lock:
            entries=self._load();found=next((x for x in entries if x['id']==identifier),None)
            if not found:return False
            if snooze:found.update(due=self.clock()+300,status='scheduled')
            else:entries.remove(found)
            self._save(entries);return True

    def command(self,text):
        text=re.sub(r'\s+',' ',text.lower()).strip(' .!?')
        text=re.sub(r'^(?:(?:hey )?sakura[, ]+)?(?:(?:can|could|would) (?:you|u) |please )*','',text)
        if not re.search(r'\b(timer|timers|alarm|alarms)\b',text):return None
        try:
            if re.match(r'^(?:show|list|check|what|how much|how long)',text):
                items=self.list()
                if not items:return 'You have no active timers or alarms.'
                return 'Active timers and alarms: '+'; '.join(f"{x['label']} — "+('ringing now' if x['status']=='ringing' else f"{x['remaining']//60} min {x['remaining']%60} sec remaining") for x in items)
            if re.match(r'^(?:cancel|delete|remove|stop|dismiss|snooze)\b',text):
                kind='timer' if re.search(r'\btimers?\b',text) else 'alarm'
                with self.lock:
                    items=[x for x in self.list() if x['kind']==kind]
                    identifier=re.search(r'\b[0-9a-f]{8}\b',text)
                    if identifier:items=[x for x in items if x['id']==identifier.group()]
                    if not items:return f'You have no matching {kind}s.'
                    if 'all' not in text:items=[next((x for x in reversed(items) if x['status']=='ringing'),items[-1])]
                    snooze=text.startswith('snooze')
                    for item in items:self.dismiss(item['id'],snooze)
                    return ('Snoozed for five minutes: ' if snooze else 'Cancelled: ')+', '.join(x['label'] for x in items)+'.'
            if not re.match(r'^(?:set|make|create|start|put|wake me|alarm|timer|\d)\b',text):return None
            if re.search(r'\btimer\b',text):
                words={'a':1,'an':1,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':11,'twelve':12,'thirteen':13,'fourteen':14,'fifteen':15,'sixteen':16,'seventeen':17,'eighteen':18,'nineteen':19,'twenty':20,'thirty':30,'forty':40,'fifty':50,'sixty':60}
                small='|'.join(key for key in words if words[key]<20)
                tens='|'.join(key for key in words if words[key]>=20)
                units='|'.join(key for key in words if 1<=words[key]<=9 and key not in ('a','an'))
                pattern=r'\b(-?\d+(?:\.\d+)?|(?:'+tens+r')(?:[ -]+(?:'+units+r'))?|(?:'+small+r'))\s*[- ]?\s*(days?|hours?|hrs?|minutes?|mins?|seconds?|secs?)\b'
                seconds=0
                for number,unit in re.findall(pattern,text):
                    amount=float(number) if re.fullmatch(r'-?\d+(?:\.\d+)?',number) else sum(words[x] for x in re.split('[ -]+',number))
                    if amount<=0:return 'Please choose a positive timer duration.'
                    if re.search(r'-\s*'+re.escape(number),text):return 'Please choose a positive timer duration.'
                    seconds+=amount*(86400 if unit.startswith('d') else 3600 if unit.startswith('h') else 60 if unit.startswith('m') else 1)
                if not 1<=seconds<=604800:return 'Tell me a timer duration between one second and seven days, such as “set a five minute timer”.'
                label=f'{int(seconds//60)} min {int(seconds%60)} sec timer'
                item=self.add('timer',self.clock()+seconds,label)
                return f"Timer set for {label.removesuffix(' timer')}. I’ll alert you while Sakura is open."
            if re.search(r'\balarm\b',text):
                if re.search(r'\b(?:on|every|daily|weekly|repeat|repeating|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',text):
                    return 'Alarm dates currently support today or tomorrow. Please say the time and one of those days.'
                for word,number in {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':11,'twelve':12}.items():
                    text=re.sub(r'\b'+word+r'\b',str(number),text)
                text=re.sub(r'\bnoon\b','12 pm',text);text=re.sub(r'\bmidnight\b','12 am',text)
                # "set an alarm 3 PM" and "alarm tomorrow at 15:00" are
                # ordinary voice requests too; the preposition is optional.
                match=re.search(r'\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\.?\b|\b(\d{1,2}):(\d{2})\b',text)
                if not match:return 'What time should I set the alarm for? Say “set an alarm for 3 PM” or “set an alarm for 15:00”.'
                if match.group(1):
                    hour,minute=int(match.group(1)),int(match.group(2) or 0)
                    if not 1<=hour<=12 or minute>59:return 'That alarm time is invalid.'
                    hour=hour%12+(12 if match.group(3)=='p' else 0)
                else:hour,minute=int(match.group(4)),int(match.group(5))
                if hour>23 or minute>59:return 'That alarm time is invalid.'
                now=datetime.fromtimestamp(self.clock());due=now.replace(hour=hour,minute=minute,second=0,microsecond=0)
                if 'today' in text and due<=now:return 'That time has already passed today. Would you like the alarm tomorrow?'
                if 'tomorrow' in text or due<=now:due+=timedelta(days=1)
                label=due.strftime('%d %B %Y at %I:%M %p')
                item=self.add('alarm',due.timestamp(),label)
                return f"Alarm set for {label}, using this PC’s local time. Keep Sakura open for the alert."
        except (OSError,ValueError,KeyError,TypeError):
            return 'I could not update the timer/alarm file. Your request was not confirmed; please try again.'
        return None


def archaeology_nudge():
    """Opt-in quiet offer, at most once per two weeks. Never create an alarm."""
    try:return _archaeology_nudge()
    except Exception:return None  # Optional memory indexing must never break actual timers/alarms.

def _archaeology_nudge():
    from memory_archaeology import service
    from atomic_state import state_lock,atomic_text
    archive=service()
    if not archive or not archive.enabled():return None
    with state_lock(archive.config):
        config=archive.settings();now=archive.clock()
        if now-config.get('last_nudge',0)<14*86400:return None
        if now-config.get('last_nudge_check',0)<86400:return None
        config['last_nudge_check']=now;atomic_text(archive.config,json.dumps(config))
        # Revalidate links from current sources before calling anything unconnected.
        archive.recall('',1)
        count=archive.unconnected()
        if count<5:return None
        config['last_nudge']=now;atomic_text(archive.config,json.dumps(config))
        return {'count':count,'message':f'You have {count} saved things older than a week with no linked records. Want to revisit what they were for?'}


def calendar_context_nudge():
    """Optional hourly read, with account binding and daily notification cooldown.

    Calendar access is separate from local saved-context opt-in. Failures never
    interrupt alarms. The MCP read is bounded to 20 upcoming events/72 hours.
    """
    try:
        return _calendar_context_nudge()
    except Exception:
        return None


def _calendar_context_nudge():
    from memory_archaeology import service
    from atomic_state import state_lock,atomic_text
    from agent_service_mcp import binding, execute
    import hashlib
    archive=service()
    if not archive or not archive.enabled():return None
    with state_lock(archive.config):
        config=archive.settings();now=archive.clock()
        if not config.get('calendar_context_enabled'):return None
        if now-config.get('last_calendar_check',0)<3600:return None
        config['last_calendar_check']=now;atomic_text(archive.config,json.dumps(config))
    account=binding('google-calendar')
    result=execute('google-calendar','calendar.events.list',{
        'account_binding':account,'calendar_id':'primary',
        'time_min':datetime.fromtimestamp(now,timezone.utc).isoformat(),
        'time_max':datetime.fromtimestamp(now+72*3600,timezone.utc).isoformat(),
        'max_results':20})
    if not isinstance(result,dict) or not result.get('ok'):return None
    events=result.get('events',[])
    if not isinstance(events,list):return None
    summaries=[{'summary':str(e.get('summary',''))[:500],'start':_event_start(e),
                'event_id':str(e.get('id',''))[:1024]} for e in events[:20] if isinstance(e,dict) and e.get('status')!='cancelled']
    matches=archive.related_to_calendar(summaries)
    if not matches or not archive.enabled() or binding('google-calendar')!=account:return None
    match=matches[0]
    signature=hashlib.sha256(json.dumps([account,match['save']['id'],match['event']['event_id'],match['event']['start']]).encode()).hexdigest()
    with state_lock(archive.config):
        config=archive.settings()
        if not config.get('calendar_context_enabled'):return None
        if signature==config.get('last_calendar_offer') or now-config.get('last_calendar_nudge',0)<86400:return None
        config.update(last_calendar_offer=signature,last_calendar_nudge=now)
        atomic_text(archive.config,json.dumps(config))
    return {'message':'Your upcoming event “'+match['event']['summary']+'” shares words with saved context “'+
            (match['save']['topic'] or match['save']['url_or_path'])[:120]+'”. Want to revisit your saves?',
            'save_id':match['save']['id'],'event_id':match['event']['event_id'],
            'relationship':'Possible text match; not proof of intent.'}


def _event_start(event):
    """Calendar all-day dates use the PC local timezone; timed events keep their offset."""
    value=event.get('start')
    if isinstance(value,dict):value=value.get('dateTime') or value.get('date')
    if isinstance(value,str):
        try:return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
        except (ValueError,OverflowError,OSError):return 0
    if isinstance(value,(int,float)) and not isinstance(value,bool):return value
    return 0


reminders=Reminders(Path(__file__).parent/'reminders.json')
