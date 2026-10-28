"""Bounded, deterministic calendar requests from Companion chat."""
import re
import threading
import time
from datetime import datetime,timedelta

MONTHS={name.lower():i for i,name in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}
def event_title(text):
    """Remove scheduling instructions, retaining the actual event description."""
    text=re.split(r'\b(?:so\s+)?(?:add|put|save|block)\s+(?:that|it|this)\b|\bit\s+(?:would|will)\s+be\b',text,maxsplit=1)[0]
    text=re.sub(r'\b\d{1,2}(?::\d{2})?\s*[ap]m\b.*','',text)
    text=re.sub(r'^(?:(?:hello|hi|hey|please)[,. ]+|i\s+have\s+(?:an?\s+)?|(?:make|create)\s+a\s+schedule\s+for\s+(?:my\s+)?|(?:remind me|set a reminder)\s+(?:about\s+)?|(?:there is|there\x27s)\s+(?:an?\s+)?)+','',text)
    text=re.sub(r'\b(?:reminder|on|at)\b',' ',text)
    text=re.sub(r'\s+',' ',text).strip(' ,.-')
    text=re.sub(r'\s+(?:from|to|until|for my|so)$','',text).strip(' ,.-')
    return text[:100] or 'Reminder'
class CalendarChat:
    def __init__(self, calendar, reminders, now=None):
        self.last_saved=None
        self.calendar=calendar;self.reminders=reminders;self.now=now or (lambda:datetime.now().astimezone());self.pending=None;self.lock=threading.RLock()
    def command(self,text):
        with self.lock:return self._command(text.strip())
    def _command(self,text):
        now=self.now();lower=text.lower().replace('’',"'").strip(' .!?\\')
        lower=re.sub(r'\btomm?or+ow\b','tomorrow',lower)
        lower=re.sub(r'\bcalender\b','calendar',lower)
        if self.pending and time.monotonic()-self.pending['created']>600:self.pending=None
        if self._agenda_request(lower):
            # Reading is not consent to a previously drafted calendar write.
            if self.pending and self.pending.get('stage')=='confirm':self.pending['stage']='review'
            return self._read_agenda(lower,now)
        if self.pending and lower in ('cancel','no','never mind','nevermind'):
            self.pending=None;return 'Cancelled. Nothing was added to Calendar.'
        if self.pending and lower in ('yes','yes please','confirm','add it','save it','go ahead'):
            item=self.pending
            if item.get('stage')!='confirm':return self._question(item)
            # Consume before network I/O; an ambiguous failure is never retried.
            self.pending=None
            try:
                result=self.calendar.create_event(item['title'],item['start'].isoformat(),item['end'].isoformat(),reminder_minutes=0)
                if not result.get('created'):return 'Calendar did not confirm the event was created. Please check it before trying again.'
                self.last_saved=self._details(item)
            except Exception:
                return 'I could not confirm the Calendar save. Check Google Calendar before trying again so we do not create a duplicate.'
            try:self.reminders.add('reminder',item['start'].timestamp(),item['title'])
            except Exception:return 'Added to Google Calendar with a notification at the start. I could not save the additional local Sakura alert.'
            return 'Added to Google Calendar: '+self._details(item)+'. I’ll also show a local alert while Sakura is running, or when you reopen it after the reminder is due.'
        date=re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+('+'|'.join(MONTHS)+r')(?:\s+(20\d{2}))?\b',lower)
        relative=re.search(r'\b(today|tomorrow)\b',lower)
        relevant=bool(re.search(r'\b(remind(?:er)?|birthday|meeting|appointment|interview|calendar|schedule)\b',lower))
        if (date or relative) and relevant:
            if not self.calendar.status().get('connected'):return 'Connect Google Calendar in Agent mode first, then tell me the reminder again.'
            try:
                if relative and not date:
                    start=(now+timedelta(days=1 if relative.group()=='tomorrow' else 0)).replace(hour=0,minute=0,second=0,microsecond=0)
                else:
                    day,month,year=date.groups();year=int(year) if year else now.year
                    start=now.replace(year=year,month=MONTHS[month],day=int(day),hour=0,minute=0,second=0,microsecond=0)
                    if not date.group(3) and start.date()<now.date():start=start.replace(year=year+1)
            except ValueError:return 'That date is invalid. Please give a valid day, month and year.'
            match=date or relative
            title=event_title(lower[:match.start()]+' '+lower[match.end():])
            self.pending={'title':title[:100],'date':start,'created':time.monotonic(),'stage':'start'}
        elif not self.pending:
            if relevant:
                connected=self.calendar.status().get('connected')
                if re.search(r'\b(add|schedule|set|make|create|remind)\b',lower) and not re.search(r'\b(did|actually)\b',lower):
                    return 'What date and start/end times should I use? Nothing has been added yet.' if connected else 'Connect Google Calendar in Agent mode first. I cannot add an event until it is connected.'
                if re.search(r'\b(added|saved|sync|connected|email|actually)\b',lower):
                    if connected and self.last_saved:return 'Google Calendar confirmed the last save: '+self.last_saved+'.'
                    return ('Google Calendar is connected. I have no confirmed save for this request. Please give the event title, date, start and end times so I can prepare it for confirmation.' if connected else 'Google Calendar is not connected. Sign in from Agent mode; I do not need your email address in chat.')
            return None
        elif not re.fullmatch(r'(?:at |until |ends at |from )?\d{1,2}(?::\d{2})?\s*[ap]m(?:\s*(?:to|until|-)\s*\d{1,2}(?::\d{2})?\s*[ap]m)?(?:\s*[, ]*(?:got it|please))?',lower):
            return self._question(self.pending) if relevant else None
        item=self.pending
        times=re.findall(r'\b(\d{1,2})(?::(\d{2}))?\s*([ap]m)\b',lower)
        if times:
            values=[]
            for hour,minute,ampm in times:
                if not 1<=int(hour)<=12 or int(minute or 0)>59:return 'Please give a valid time such as 2 pm or 2:30 pm.'
                values.append(item['date'].replace(hour=int(hour)%12+(12 if ampm=='pm' else 0),minute=int(minute or 0)))
            if len(values)>1:item['start'],item['end']=values[:2]
            elif item['stage']=='end':item['end']=values[0]
            else:
                item['start']=values[0]
                if len(values)>1:item['end']=values[1]
                elif 'birthday' in item['title']:item['end']=values[0]+timedelta(minutes=15)
            if 'end' in item and item['end']<=item['start']:
                item.pop('end');item['stage']='end';return 'The end must be later than the start on that date. What time does it end?'
            item['stage']='confirm' if 'end' in item else 'end'
        return self._question(item)

    @staticmethod
    def _agenda_request(text):
        if re.search(r'\b(?:add|create|book|reschedule|move|delete|remove|cancel|remind|save)\b|\b(?:set|make) (?:a |my )?(?:reminder|meeting|schedule)\b',text):return False
        if re.search(r'\b(?:how to|should i|help me) (?:plan|schedule)\b',text):return False
        subject=bool(re.search(r'\b(?:plans?|schedule|agenda|calendar|events?|appointments?|meetings?)\b',text))
        reading=bool(re.search(r"\b(?:what(?:'s| is| are)?|show|tell|read|check|list|view|see|any|do i have|am i free)\b",text))
        personal=bool(re.search(r'\b(?:my|me|i|today|tomorrow|this week|next week|next 7 days)\b',text))
        shorthand=bool(re.fullmatch(r"(?:(?:my|today's|tomorrow's) )?(?:schedule|agenda|plans?|calendar)(?: for)?(?: today| tomorrow| this week| next week)?",text))
        activity=bool(re.search(r"\b(?:what (?:do i have|am i doing)|am i free|do i have anything)\b",text) and re.search(r'\b(?:today|tomorrow|this week)\b',text))
        return (subject and reading and personal) or shorthand or activity

    def _read_agenda(self,text,now):
        try:
            if not self.calendar.status().get('connected'):
                return 'Google Calendar is not connected with Calendar access. Open Agent mode > Google sign-in to connect it, then ask me again.'
            start=now.replace(hour=0,minute=0,second=0,microsecond=0)
            label='today'
            explicit=re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+('+'|'.join(MONTHS)+r')(?:\s+(20\d{2}))?\b',text)
            if explicit:
                day,month,year=explicit.groups()
                try:start=start.replace(year=int(year) if year else now.year,month=MONTHS[month],day=int(day))
                except ValueError:return 'That date is invalid. Please give a valid day, month and year.'
                label=start.strftime('%d %B %Y')
            elif 'tomorrow' in text:
                start+=timedelta(days=1);label='tomorrow'
            elif 'next week' in text:
                start+=timedelta(days=7-start.weekday());label='next week'
            elif 'this week' in text:
                start-=timedelta(days=start.weekday());label='this week'
            days=7 if label in ('this week','next week') or 'next 7 days' in text else 1
            if 'next 7 days' in text:label='the next 7 days'
            end=start+timedelta(days=days)
            result=self.calendar.list_events(time_min=start.isoformat(),time_max=end.isoformat(),max_results=50)
            if result.get('ok') is not True:raise ValueError('Calendar read was not confirmed')
        except Exception:
            return 'I could not read Google Calendar just now. Check your connection and Google sign-in in Agent mode, then try again. I have not changed any events.'
        events=[event for event in result.get('events',[]) if event.get('status')!='cancelled']
        if not events:return f'You have no events on your connected Google Calendar for {label}. That only covers this calendar, not plans saved elsewhere.'
        offset=now.strftime('%z');zone='UTC'+offset[:3]+':'+offset[3:]
        lines=[f'Your Google Calendar schedule for {label} ({zone}):']
        for event in events[:12]:
            title=re.sub(r'\s+',' ',str(event.get('summary') or 'Untitled event')).strip()[:160]
            begins=event.get('start') or {};ends=event.get('end') or {}
            if begins.get('date'):
                when='All day'
                if days>1:when=begins['date']+' - '+when
            else:
                try:
                    stamp=datetime.fromisoformat(begins['dateTime'].replace('Z','+00:00'))
                    if stamp.tzinfo is None:raise ValueError('Missing event timezone')
                    stamp=stamp.astimezone(now.tzinfo)
                    when=stamp.strftime('%I:%M %p').lstrip('0')
                    if days>1 or stamp.date()!=start.date():when=stamp.strftime('%d %b')+' '+when
                    if ends.get('dateTime'):
                        finish=datetime.fromisoformat(ends['dateTime'].replace('Z','+00:00'))
                        if finish.tzinfo is not None:
                            finish=finish.astimezone(now.tzinfo)
                            when+=' - '+(finish.strftime('%d %b ') if finish.date()!=stamp.date() else '')+finish.strftime('%I:%M %p').lstrip('0')
                except (KeyError,ValueError,TypeError):when='Time unavailable'
            lines.append(f'{when}: {title}')
        if len(events)>12:lines.append('More events are on your calendar; open Google Calendar for the full list.')
        return '\n'.join(lines)
    def _details(self,item):
        return f"{item['title']} on {item['start']:%d %B %Y}, {item['start']:%I:%M %p}–{item['end']:%I:%M %p} ({item['start']:%Z}, UTC{item['start']:%z})"
    def _question(self,item):
        if item['stage']=='start':return f"What time on {item['date']:%d %B %Y} should I remind you? Give a time such as 9 am; I cannot detect when you personally wake up."
        if item['stage']=='end':return 'What time does the meeting or appointment end?'
        if item['stage']=='review':item['stage']='confirm'
        return 'Add '+self._details(item)+' to Google Calendar with a notification at the start? Say yes to save, or cancel.'

_instance=None
_instances={}

def calendar_command(text,channel="desktop"):
    global _instance
    if channel=='desktop':
        if _instance is None:
            from agent_calendar import google_calendar
            from assistant_reminders import reminders
            _instance=CalendarChat(google_calendar,reminders)
        return _instance.command(text)
    if channel not in _instances:
        from agent_calendar import google_calendar
        from assistant_reminders import reminders
        _instances[channel]=CalendarChat(google_calendar,reminders)
    return _instances[channel].command(text)
