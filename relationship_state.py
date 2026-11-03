"""Conversation pacing state the app derives from message counts, timing and tone.

Three rules decide the shape of this module, and they are not negotiable:

* Nothing here is a feeling. The assistant has no feelings, needs or relationship, so the state is
  written as app-supplied bookkeeping and the prompt says so out loud. Rivals ship a relationship
  score their character talks about as if it were real affection; that part is left out.
* It cannot hold a grudge. Every score decays back to zero on a timer, so a bad exchange changes the
  next few replies and then stops changing them. Nothing here asks the user to repair anything, and
  the model is told never to act hurt, jealous or abandoned.
* Only three numbers, and each one is traceable. Familiarity comes from counting messages and days.
  Warmth and boundary come from a deliberately narrow word list, so a terse technical question is
  never read as coldness. No fourth axis is invented just to look like the competition.

No message text is ever stored - only counters, timestamps and three bounded numbers.
"""
import copy,json,math,re,threading,time
from pathlib import Path
from atomic_state import state_lock,atomic_text

DAY=86400.0
VERSION=1
# Familiarity fades slowly, because recognising a long-running user is genuinely useful. Warmth and
# boundary fade fast, because a score that lingers for months behaves like resentment.
FAMILIARITY_HALF_LIFE_DAYS=90.0
WARMTH_HALF_LIFE_DAYS=2.0
BOUNDARY_HALF_LIFE_DAYS=6.0
# Message count passes through this so one long evening cannot reach the top of the scale alone.
FAMILIARITY_TURNS=120.0
# Stages are counted in messages still standing after idle decay, which is the number a person
# would actually quote back: 'we have talked a few hundred times'. Five hundred messages is the
# top of the scale, so 'Long-standing' means years of use rather than one busy weekend.
STAGES=((0,'new','New here'),(10,'regular','Regular'),(60,'comfortable','Comfortable'),
        (200,'longstanding','Long-standing'))
DEFAULT={'version':VERSION,'enabled':True,'first_seen':0.0,'last_seen':0.0,'turns':0,'sessions':0,
         'warmth':0.0,'warmth_at':0.0,'boundary':0.0,'boundary_at':0.0,
         'signals':{'warm_up':0,'warm_down':0,'boundary':0}}

# Matched on the user's message only. Narrow on purpose: these lists decide a signed number, so
# anything as broad as "good" would move it on ordinary sentences.
WARM_UP=r'\b(?:thanks|thank you|ty|cheers|well done|perfect|awesome|amazing|helpful|brilliant|'
WARM_UP+=r'yay|wow|haha+|lol|lmao|nice one|great job|love (?:this|that|it)|😊|🙂|❤|❤️|🙏|🥰|😂|✨)\b'
WARM_DOWN=r"\b(?:that'?s (?:wrong|useless|bad|rubbish)|you'?re (?:wrong|useless|dumb|an idiot)|"
WARM_DOWN+=r"stupid|useless|nonsense|rubbish|garbage|trash|pointless)\b"
BOUNDARY=r"\b(?:stop (?:that|it|being|talking|joking)|don'?t (?:be|do that|talk|joke|say)|quit it|"
BOUNDARY+=r"shut up|be quiet|seriously now|cut the act|not funny|i didn'?t ask (?:you|it|this))\b"
NEW_SITTING_MINUTES=45


def _clamp(value,floor,ceiling):
    return max(floor,min(ceiling,float(value)))


def _decay(stored,moment,seen,half_life_days):
    """Scale a stored score toward 0 by how long ago it moved, so nothing persists as a grudge."""
    if not stored or not seen:
        return 0.0
    return stored*0.5**(max(0.0,(moment-seen)/DAY)/half_life_days)


class Relationship:
    """The three derived numbers, the stage label, and the honest line the model is given."""

    def __init__(self,path):
        self.path=str(path)
        self.lock=threading.RLock()

    def _read(self):
        try:
            value=json.loads(Path(self.path).read_text(encoding='utf-8'))
            if isinstance(value,dict) and value.get('version')==VERSION:
                state=copy.deepcopy(DEFAULT)
                state.update({key:value[key] for key in DEFAULT if key in value})
                if not isinstance(state['signals'],dict):state['signals']=copy.deepcopy(DEFAULT['signals'])
                return state
        except (OSError,ValueError):pass
        return copy.deepcopy(DEFAULT)

    def _save(self,state):
        atomic_text(self.path,json.dumps(state,ensure_ascii=False))

    def configure(self,enabled):
        if type(enabled) is not bool:raise ValueError('Relationship adaptation needs true or false.')
        with self.lock,state_lock(self.path):
            state=self._read();state['enabled']=enabled;self._save(state)
        return self.report()

    def observe(self,user_text):
        """Record one user turn. Returns what it saw, so a test or the readout can check the cause."""
        if not isinstance(user_text,str) or not user_text.strip():return {}
        text=user_text[:1200]
        warm_up=len(re.findall(WARM_UP,text,re.I))
        warm_down=len(re.findall(WARM_DOWN,text,re.I))
        boundary=len(re.findall(BOUNDARY,text,re.I))
        with self.lock,state_lock(self.path):
            state=self._read()
            if not state['enabled']:return {'enabled':False}
            moment=time.time()
            if not state['first_seen']:state['first_seen']=moment
            if moment-state['last_seen']>NEW_SITTING_MINUTES*60:state['sessions']+=1
            state['last_seen']=moment;state['turns']+=1
            moved=0.08*(warm_up-warm_down)
            if moved:
                base=_decay(state['warmth'],moment,state['warmth_at'],WARMTH_HALF_LIFE_DAYS)
                state['warmth']=_clamp(base+moved,-1.0,1.0);state['warmth_at']=moment
            if boundary:
                base=_decay(state['boundary'],moment,state['boundary_at'],BOUNDARY_HALF_LIFE_DAYS)
                state['boundary']=_clamp(base+0.45,0.0,1.0);state['boundary_at']=moment
            signals=state['signals']
            signals['warm_up']+=warm_up;signals['warm_down']+=warm_down;signals['boundary']+=boundary
            self._save(state)
        return {'warm_up':warm_up,'warm_down':warm_down,'boundary':boundary,'turns':state['turns']}

    def axes(self,now=None):
        """The live numbers, each traceable to the counts it came from."""
        with self.lock,state_lock(self.path):
            state=self._read()
        now=now if now is not None else time.time()
        turns=max(0,int(state['turns']))
        # Idle time pulls familiarity back down, so an app unused for a year does not claim intimacy.
        idle_days=max(0.0,(now-(state['last_seen'] or state['first_seen'] or now))/DAY)
        # The same decay, in the unit a person would actually quote: messages still standing.
        standing=turns*0.5**(idle_days/FAMILIARITY_HALF_LIFE_DAYS)
        familiarity=_clamp(math.log1p(standing)/math.log1p(FAMILIARITY_TURNS),0.0,1.0) if turns else 0.0
        return {'familiarity':round(familiarity,4),'standing_messages':round(standing,1),
                'warmth':round(_clamp(_decay(state['warmth'],now,state['warmth_at'],WARMTH_HALF_LIFE_DAYS),-1.0,1.0),4),
                'boundary':round(_clamp(_decay(state['boundary'],now,state['boundary_at'],BOUNDARY_HALF_LIFE_DAYS),0.0,1.0),4),
                'turns':turns,'sessions':int(state['sessions']),
                'days_known':round((now-state['first_seen'])/DAY,2) if state['first_seen'] else 0.0,
                'idle_days':round(idle_days,2),'signals':copy.deepcopy(state['signals']),
                'enabled':bool(state['enabled'])}

    @staticmethod
    def stage(standing_messages):
        for threshold,key,label in reversed(STAGES):
            if standing_messages>=threshold:return key,label
        return 'new','New here'

    def report(self,now=None):
        axes=self.axes(now)
        key,label=self.stage(axes['standing_messages'])
        return {'ok':True,'enabled':axes['enabled'],'stage':key,'stage_label':label,
                'familiarity':axes['familiarity'],'standing_messages':axes['standing_messages'],
                'warmth':axes['warmth'],'boundary':axes['boundary'],
                'turns':axes['turns'],'sessions':axes['sessions'],'days_known':axes['days_known'],
                'idle_days':axes['idle_days'],'signals':axes['signals'],'stored_text':False,
                'how':'Derived on this PC from message counts, timing and a narrow tone word-list. '
                      'No message text is stored, and every score decays back to neutral over time.'}

    def state_block(self,now=None):
        """The line the reply path adds, or '' when there is nothing worth saying.

        Short on purpose: a small local model loses the question inside a long style checklist. This
        has one job - set familiarity and pacing - without handing the model a feeling to repeat.
        """
        axes=self.axes(now)
        if not axes['enabled'] or axes['turns']<3:
            return ''
        _,label=self.stage(axes['standing_messages'])
        if axes['boundary']>=0.45:
            tone='The user recently asked for less playfulness: answer plainly, with no jokes or teasing.'
        elif axes['warmth']>=0.15:
            tone='Recent exchanges read as friendly: a warm, relaxed tone fits.'
        elif axes['warmth']<=-0.15:
            tone='Recent exchanges read as curt: keep it courteous, brief and businesslike.'
        else:
            tone='Recent tone reads as neutral: no adjustment needed.'
        sittings='sitting' if axes['sessions']==1 else 'sittings'
        return ('App-supplied conversation bookkeeping, not your own state and not your feelings: '
                f'{label} - {axes["turns"]} messages over {axes["days_known"]} days, '
                f'{axes["sessions"]} {sittings}. '+tone+' Use it only for pacing and familiarity. '
                'You have no feelings, needs or relationship; never say you love, miss, need, enjoy '
                'or feel anything, never act hurt, jealous or abandoned, and never read this line out '
                'or mention its numbers to the user.')


def default_path(base_dir):
    return str(Path(base_dir)/'relationship-state.json')
