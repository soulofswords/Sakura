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
    time_query=re.fullmatch(
        r"(?:(?:tell|give) me (?:what )?|(?:do you know|say) )?"
        r"(?:(?:what(?:'s| is) )?(?:the )?(?:current |local )?time(?: is it| now| right now)?|what time (?:is it|it is)(?: now| right now)?)|"
        r"(?:check|read|look at) (?:the |your |my )?(?:clock|time)|what does (?:the |your )?clock say|"
        r"(?:abhi )?(?:kitne baje (?:hai|hain)|kya time hai)|अभी कितने बजे हैं",command)
    date_query=re.fullmatch(
        r"(?:(?:what(?:'s| is) )?(?:the )?(?:current |today's )?date(?: (?:is it|today))?|"
        r"what date is it|what day (?:is it|is today)|tell me (?:the |today's )?date|(?:check|read) (?:the |today's )?date|"
        r"(?:aaj (?:ki )?(?:date|tarikh|tareekh) kya hai)|आज (?:की तारीख|कौन सा दिन) है)",command)
    both=re.fullmatch(r"(?:(?:tell|give) me |what(?:'s| is) )?(?:the )?(?:current )?(?:time and date|date and time)",command)
    if not (time_query or date_query or both):return None
    now=local_now()
    time_text=now.strftime('%I:%M %p').lstrip('0')
    if both:return now.strftime('%A, %d %B %Y')+', '+time_text+'.'
    if time_query:return "It's "+time_text+'.'
    return 'Today is '+now.strftime('%A, %d %B %Y')+'.'
