"""Fresh PC clock context, independent of model knowledge and web access."""
from datetime import datetime
import re


def local_now():
    return datetime.now().astimezone()


def clock_context():
    now=local_now()
    return ('Current PC clock: '+now.strftime('%A, %d %B %Y, %I:%M %p %Z (UTC%z)')+'. '
            'This is a fresh local system reading. You can read the clock and date; do not claim you cannot. '
            'Use it when relevant, but do not volunteer time/date or ask the user to check the clock in unrelated conversation.')


def clock_command(command):
    command = re.sub(r'\s+', ' ', str(command).lower().replace('’', "'")).strip().rstrip('.!?')
    command = re.sub(r'^(?:so\s+|(?:can|could|would) you (?:please )?)+', '', command)
    # A second question must not send a factual clock request back to the LLM.
    clauses=re.split(r"[?.!]+\s*|\s+and\s+",command,maxsplit=1)
    if len(clauses)==2 and clauses[1].strip():
        first=clock_command(clauses[0].strip())
        if first and re.search(r'\b(?:historical|history|happened|on this day)\b',clauses[1]):
            return first+'\n\n'+historical_events(local_now())
    time_query=re.fullmatch(
        r"(?:(?:tell|give) me (?:what )?|(?:do you know|say) )?"
        r"(?:(?:what(?:'s| is) )?(?:the )?(?:current |local )?time(?: is it| now| right now)?|what time (?:is it|it is)(?: now| right now)?)|"
        r"(?:check|read|look at) (?:the |your |my )?(?:clock|time)|what does (?:the |your )?clock say|"
        r"(?:abhi )?(?:kitne baje (?:hai|hain)|kya time hai)|अभी कितने बजे हैं",command)
    date_query=re.fullmatch(
        r"(?:(?:what(?:'s| is) )?(?:the )?(?:current |today's )?date(?: (?:is it|today))?|"
        r"what date is it|what day (?:is it|is today)|tell me (?:the |today's )?date|(?:check|read) (?:the |today's )?date|"
        r"(?:aaj (?:ki )?(?:date|tarikh|tareekh) kya hai)|आज (?:की तारीख|कौन सा दिन) है)",command)
    both=re.fullmatch(r"(?:(?:tell|give) me (?:what(?:'s| is) )?|what(?:'s| is) )?(?:the )?(?:current |today's )?(?:time and date|date and time)(?: (?:now|today|right now))?",command)
    if not (time_query or date_query or both):return None
    now=local_now()
    time_text=now.strftime('%I:%M %p').lstrip('0')
    if both:return now.strftime('%A, %d %B %Y')+', '+time_text+'.'
    if time_query:return "It's "+time_text+'.'
    return 'Today is '+now.strftime('%A, %d %B %Y')+'.'


def historical_events(now):
    """Read dated historical references; a failed lookup is never 'nothing happened'."""
    import requests
    try:
        response=requests.get(
            f'https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/{now.month:02d}/{now.day:02d}',
            headers={'User-Agent':'Sakura/1.0 (user-requested historical reference)'},timeout=8)
        response.raise_for_status()
        events=response.json().get('events',[])
        lines=[]
        for event in events:
            year=event.get('year')
            if not isinstance(year,int) or year>=now.year:continue
            for page in event.get('pages',[]):
                url=page.get('content_urls',{}).get('desktop',{}).get('page','')
                if not url.startswith('https://en.wikipedia.org/wiki/'):continue
                text=' '.join(str(event.get('text','')).split())[:600]
                if text:lines.append(f'- {year}: {text} Source: {url}')
                break
            if len(lines)==3:break
        if lines:return 'On this date in history:\n'+'\n'.join(lines)
    except (requests.RequestException,ValueError,TypeError,AttributeError):
        pass
    return "I couldn't retrieve verified historical events right now. I can still read today's date from your PC clock."
