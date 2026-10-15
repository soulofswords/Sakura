"""Explicit avatar dance requests; no generated text executes animations."""
import re

def hand_action(text):
    command=text.lower().replace('’',"'").strip()
    if re.search(r"\b(?:don't|do not|stop|never)\b",command):return None
    if not re.fullmatch(r"(?:(?:hey )?sakura[, ]+)?(?:(?:can|could|would|will) (?:you|u) |please )*"
                        r"(?:show|raise|lift|hold up)\s+(?:(?:me|us)\s+)?(?:both\s+)?(?:your\s+|ur\s+|the\s+)?"
                        r"(?:(both|left|right)\s+)?hands?(?:\s+(?:to me|for me|please|up))*[.!? ]*",command):return None
    side=re.search(r'\b(left|right)\b',command)
    return 'hand_'+side.group(1) if side else 'hands_both'

def hand_reply(action,language='English',supported=True):
    if not supported:return {'Hindi':'हाथ दिखाने के लिए पहले रिग वाला PMX या VRM मॉडल चुनिए।',
        'Hinglish':'Haath dikhane ke liye pehle rig wala PMX ya VRM model select karo.'}.get(language,'Select a rigged PMX or VRM model so I can show my hands.')
    side={'hand_left':'left hand','hand_right':'right hand','hands_both':'both hands'}[action]
    if language=='Hindi':return {'hand_left':'यह मेरा बायाँ हाथ है।','hand_right':'यह मेरा दायाँ हाथ है।','hands_both':'ये रहे मेरे दोनों हाथ।'}[action]
    if language=='Hinglish':return {'hand_left':'Yeh mera left haath hai.','hand_right':'Yeh mera right haath hai.','hands_both':'Yeh rahe mere dono haath.'}[action]
    return 'Here '+('are my ' if action=='hands_both' else 'is my ')+side+'.'

def dance_action(text):
    lower=text.strip().lower()
    if not re.search(r'\bdanc(?:e|ing)\b|नाच|डांस|\bnaach|\bnach[o]?\b',lower):return None
    if re.search(r'\b(?:stop|cancel|don\x27t|do not|mat|band)\b|बंद|मत',lower):return 'stop'
    if not re.search(r'can (?:you|u)|could (?:you|u)|will (?:you|u)|please|show|do (?:a|the)|make (?:you|u)|for me|करो|कर सकती|नाचो|\b(?:karo|dikhao|sakti|sakte|naacho|nacho)\b',lower) and not re.fullmatch(r'(?:sakura[, ]+)?(?:dance|naach|nacho|डांस|नाचो)(?:[!. ]*)',lower):return None
    if 'wave' in lower:return 'wave'
    if re.search(r'step|side|shuffle',lower):return 'step'
    return 'groove'

def dance_reply(action,language='English',supported=True):
    if not supported:
        return {'Hindi':'मास्टर, नृत्य के लिए पहले एक रिग वाला PMX या VRM मॉडल चुनिए।',
                'Hinglish':'Master, dance ke liye pehle ek rig wala PMX ya VRM model select karo.'}.get(language,'Master, select a rigged PMX or VRM model first so I can dance.')
    if action=='stop':
        return {'Hindi':'ठीक है मास्टर, नृत्य रोक रही हूँ।','Hinglish':'Theek hai Master, dance rok rahi hoon.'}.get(language,'Okay, Master, stopping the dance.')
    return {'Hindi':'हाँ मास्टर, देखिए मेरा छोटा सा नृत्य!','Hinglish':'Haan Master, dekho mera chhota sa dance!'}.get(language,'Of course, Master! Here comes a little dance.')
