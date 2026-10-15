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
    if not re.search(r'\bdanc(?:e|ing)\b|नाच|डांस|\bnaach|\bnach[o]?\b',lower):
        named=re.search(r'\b(twist|disco|march|moonwalk|ballet|tango|salsa|breakdance|waltz|twerk)\b',lower)
        if named and re.search(r'\b(?:can|could|please|do|try|show|switch|change)\b',lower):
            return named.group(1) if named.group(1) in ('twist','disco','march') else 'unsupported'
        return None
    if re.search(r'\b(?:stop|cancel|don\x27t|do not|mat|band)\b|बंद|मत',lower):return 'stop'
    for style,pattern in [('twist',r'\btwist\b'),('disco',r'\bdisco\b'),('march',r'\bmarch(?:ing)?\b')]:
        if re.search(pattern,lower):return style
    if not re.search(r'change|switch|can (?:you|u)|could (?:you|u)|will (?:you|u)|please|show|do (?:a|the)|make (?:you|u)|for me|करो|कर सकती|नाचो|\b(?:karo|dikhao|sakti|sakte|naacho|nacho)\b',lower) and not re.fullmatch(r'(?:sakura[, ]+)?(?:dance|naach|nacho|डांस|नाचो)(?:[!. ]*)',lower):return None
    if 'wave' in lower:return 'wave'
    if re.search(r'step|side|shuffle',lower):return 'step'
    if 'groove' in lower:return 'groove'
    # Only generic dance requests default to Groove. An unknown named move
    # must not be presented as though it were a supported routine.
    generic={'can','could','would','will','you','u','please','show','me','us','do','a','the','make','your','for','dance','dancing','little','bit','some','sakura','now','here','one','to','style','change','switch','routine','other','another','different','moves','move','kya','tum','kar','sakti','sakte','ho','karo','dikhao','naach','nacho','i','want','see','it'}
    if set(re.findall(r'[a-z]+',lower))-generic:return 'unsupported'
    return 'groove'

def dance_style_followup(text,current=None):
    if not current:return None
    lower=text.strip().lower()
    if not re.search(r'\b(?:change|switch|try|another|different)\b',lower):return None
    for style in ['twist','disco','march']:
        if re.search(r'\b'+style+r'\b',lower):return style
    if re.search(r'\bwave\b',lower):return 'wave'
    if re.search(r'\b(?:step|shuffle)\b',lower):return 'step'
    if 'groove' in lower:return 'groove'
    if re.search(r'\b(?:style|dance|move|routine)\b',lower) or re.fullmatch(r'(?:please )?(?:try|do|show me|switch to) (?:another(?: one)?|a different one|something different)[.!? ]*',lower):
        styles=['groove','step','wave','twist','disco','march']
        return styles[(styles.index(current)+1)%len(styles)] if current in styles else 'groove'
    return None

def dance_reply(action,language='English',supported=True):
    if not supported:
        return {'Hindi':'मास्टर, नृत्य के लिए पहले एक रिग वाला PMX या VRM मॉडल चुनिए।',
                'Hinglish':'Master, dance ke liye pehle ek rig wala PMX ya VRM model select karo.'}.get(language,'Master, select a rigged PMX or VRM model first so I can dance.')
    if action=='stop':
        return {'Hindi':'ठीक है मास्टर, नृत्य रोक रही हूँ।','Hinglish':'Theek hai Master, dance rok rahi hoon.'}.get(language,'Okay, Master, stopping the dance.')
    label={'groove':'Groove','step':'Side step','wave':'Arm wave','twist':'Twist','disco':'Disco','march':'March'}[action]
    hindi={'groove':'ग्रूव','step':'साइड स्टेप','wave':'आर्म वेव','twist':'ट्विस्ट','disco':'डिस्को','march':'मार्च'}[action]
    return {'Hindi':f'हाँ, अब {hindi} नृत्य कर रही हूँ।','Hinglish':f'Haan, ab {label} dance kar rahi hoon.'}.get(language,f'Here comes {label}.')
