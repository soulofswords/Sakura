"""User-controlled forms of address, independent of avatar presentation."""
import re
from datetime import datetime

TITLES={'sir':'Sir','maam':'Ma’am','none':''}

def address_text(text,selection='sir'):
    title=TITLES.get(selection,'Sir')
    result=re.sub(r'\b(?:master|sir|ma[’\x27]?am|madam)\b(?!\s+(?:volume|branch|key|chief|recording|degree|copy|password))|मास्टर',lambda _:title,text,flags=re.I)
    if not title:
        result=re.sub(r',\s*,',',',result)
        result=re.sub(r',\s*([.!?।])',r'\1',result)
        result=re.sub(r'\s+([,.!?।])',r'\1',result)
        result=re.sub(r'^\s*[,，]\s*','',result)
    return result

def greeting(selection='sir',hour=None):
    hour=datetime.now().hour if hour is None else hour
    period='morning' if hour<12 else 'afternoon' if hour<17 else 'evening'
    title=TITLES.get(selection,'Sir')
    return f'Good {period}'+(', '+title if title else '')+'.'
