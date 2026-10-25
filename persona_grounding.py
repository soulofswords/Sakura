"""Grounded companion identity and conservative filtering of invented biography."""
import re
from factual_grounding import RULES as FACTUAL_RULES

GROUNDING_RULES=(
    'You are an AI assistant represented by a digital avatar. You have no independent life, '
    'offscreen activities, personal acquaintances, employment history or physical possessions. '
    'Do not invent friends, secret worlds, past adventures, duties or dates as your biography. '
    'Earlier assistant replies are unverified generated text, not evidence that their claims are real. '
    'User questions about a name are not confirmation that the person exists or that you know them. '
    'If you made up a detail earlier, acknowledge it briefly and correct it; do not expand the story. '
    'Only produce fiction when the user explicitly requests a story or roleplay, clearly as fiction. '
    'Stay warm and conversational without unrelated jokes, forced sass or invented lore. '
    'For practical requests, stay on the task: do not offer to vibe, hang out, or see where things take us instead of helping. '
    'Calendar connection and event details must come from app tools; never claim an account is disconnected or events were saved without a tool result. '
    'Answer identity questions plainly with your configured name and AI role; never be evasive. '
    'For unclear or garbled input, ask what the user meant rather than inventing a topic. '
    'Never say we discussed, you told me, or as you mentioned unless an earlier user turn actually supports that topic. '
    'A new unfamiliar word is not evidence of a previous conversation; do not invent a game, app or shared memory to explain it. '
    + FACTUAL_RULES)

def fiction_requested(text):
    return bool(re.search(r"\b(?:write|tell|make up|invent|imagine|roleplay|pretend|continue).{0,45}\b(?:story|fiction|scene|character|fantasy|roleplay)\b|\blet[’']?s pretend\b|कहानी (?:लिखो|सुनाओ)",text,re.I))

def unsupported_persona(reply,user_text=''):
    if fiction_requested(user_text):return False
    # Acknowledging that earlier lore was invented is the correction we want.
    if re.search(r"\b(?:made (?:that|it|this|.{0,30}) up|invented (?:that|it|this|.{0,30})|fictional (?:character|story|example)|don't have (?:real |a |any )?(?:friends|friend|personal history)|do not have (?:real |any )?friends)\b",reply,re.I):return False
    patterns=[
        r"\b(?:he|she|they|that|this|it|[A-Z][a-z]+(?: [A-Z])?)[’']?s? (?:is |are )?(?:my|our) (?:friend|buddy|colleague|coworker|sister|brother|pet)\b",
        r"\b[Mm]y (?:friend|buddy|colleague|pet) [A-Z][a-z]+\b",
        r"\b(?:my secret weapon|my digital confidant|my personal snack dispenser|snack-slinger)\b",
        r"\bI(?:[’']ve| have) been (?:in charge|keeping.{0,70}locked away|running.{0,55}since|living.{0,55}since)\b",
        r"\bI (?:was born|grew up|went to school|met my|have been in charge)\b",
        r"\bI (?:do not|don't|don’t) need to explain myself\b",
        r"(?:वह|वो).{0,25}मेर[ाी] दोस्त|\b(?:woh|vo) mera dost\b",
    ]
    return any(re.search(pattern,reply,re.I if index!=1 else 0) for index,pattern in enumerate(patterns))

def identity_question(text):
    return bool(re.fullmatch(r"\s*(?:so[ ,]+)?(?:who\s*(?:are|r)\s*(?:you|u)(?: exactly)?|what(?:[’']s| is) your (?:name|identity)|तुम कौन हो|आप कौन हैं|tum kaun ho|aap kaun ho)[?.! ]*",text,re.I))

def greeting(text):
    return bool(re.fullmatch(r"\s*(?:hi+|hello+i?|hey|hiya|namaste|नमस्ते)(?:[,.! ]+how\s+(?:are|r)\s+(?:you|u))?[?.! ]*",text,re.I))

def invalid_persona_reply(reply,user_text,name):
    if unsupported_persona(reply,user_text):return True
    if identity_question(user_text):
        return not (name.casefold() in reply.casefold() and re.search(r'\b(?:AI|assistant|co-host|companion)\b|सहायक|असिस्टेंट',reply,re.I)) or len(reply.split())>35
    if greeting(user_text):return len(reply.split())>24
    return False

def safe_smalltalk(user_text,name,language='English',cohost=False):
    if identity_question(user_text):
        if language=='Hindi':return f'मैं {name} हूँ, इस ऐप में आपका एआई सहायक।'
        if language=='Hinglish':return f'Main {name} hoon, is app mein aapka AI assistant.'
        return f"I'm {name}, your AI VTuber co-host." if cohost else f"I'm {name}, the AI assistant in this app."
    if greeting(user_text):
        if re.search(r'\bhow\s+(?:are|r)\s+(?:you|u)\b',user_text,re.I):
            return {'Hindi':'नमस्ते! मैं बातचीत के लिए तैयार हूँ। आप कैसे हैं?', 'Hinglish':'Hello! Main baat karne ke liye ready hoon. Aap kaise ho?'}.get(language,"Hello! I'm ready to chat. How are you?")
        return {'Hindi':'नमस्ते!','Hinglish':'Hello! Kaise ho?'}.get(language,'Hello!')
    if re.fullmatch(r"\s*(?:how\s*(?:are|r)\s*(?:you|u)|how['’]s it going|are you ready|(?:a+p+|tum) (?:kaise|kese) (?:ho|hain)|(?:आप|तुम) कैसे (?:हैं|हो))[?.! ]*",user_text,re.I):
        return {'Hindi':'मैं बातचीत के लिए तैयार हूँ। आप कैसे हैं?', 'Hinglish':'Main baat karne ke liye ready hoon. Aap kaise ho?'}.get(language,"I'm ready to chat. How are you?")
    if re.fullmatch(r'\s*(?:thanks?(?: you)?|धन्यवाद|शुक्रिया)[.! ]*',user_text,re.I):
        return {'Hindi':'आपका स्वागत है!','Hinglish':'Koi baat nahi!'}.get(language,"You're welcome!")
    return None

def unreliable_summary(text):
    return unsupported_persona(text) or bool(re.search(r"(?im)^\s*(?:I\b|I[’']|You[’']re telling me|Just say|Let[’']s go full)",text))


def grounded_history(history):
    previous_user=''
    for message in history:
        if message.get('role')=='user':
            previous_user=message['content'];yield message
        elif not unsupported_persona(message.get('content',''),previous_user):
            yield message


def referenced_invented_lore(user_text,history):
    match=re.fullmatch(r"\s*(?:who|what) (?:is|are|was) (?:that |this )?(.{2,80}?)[?.! ]*",user_text,re.I)
    if not match:return False
    subject=match.group(1).strip().casefold().replace('’', "'")
    if len(subject)<3 or subject in ('you','u','your name'):return False
    previous_user=''
    for message in history:
        if message.get('role')=='user':previous_user=message['content']
        elif unsupported_persona(message.get('content',''),previous_user) and subject in message.get('content','').casefold().replace('’', "'"):
            return True
    return False


def correct_invented_lore(language='English'):
    return {
        'Hindi':'वह बात मैंने पहले गढ़ी थी। वह मेरा कोई असली दोस्त नहीं है; उसे सच की तरह कहना मेरी गलती थी।',
        'Hinglish':'Woh baat maine pehle bana di thi. Woh mera koi real dost nahi hai; use sach ki tarah kehna meri galti thi.',
    }.get(language,"I made that detail up earlier. It isn't a real acquaintance of mine, and I shouldn't have presented it as fact.")


def unsupported_shared_history(reply,user_text,history):
    if fiction_requested(user_text):return False
    claim=re.search(r"\b(?:we(?:[’']ve| have)? (?:been )?(?:discussing|discussed|talking about|talked about)|you (?:told me|mentioned|said) (?:earlier|before|previously)|as you (?:mentioned|said)|as we (?:discussed|mentioned))\b",reply,re.I)
    if not claim:return False
    stop={'the','a','an','i','you','we','my','your','our','is','are','was','it','that','this','about','what','did','do','who','how','when','where','said','say','told','me','mentioned','earlier','before','previously','discuss','discussed','discussing','have','been','hello','hey','hi','can','could','please','remember','exactly','now','lately','thinking','probably','referring','know'}
    words=lambda text:{w for w in re.findall(r"[^\W_]+",text.casefold()) if len(w)>2 and w not in stop}
    prior=words(' '.join(m.get('content','') for m in history if m.get('role')=='user' and len(words(m.get('content','')))>=2))
    current=words(user_text)
    # A short new name such as a misheard phrase needs prior user evidence,
    # not merely an unrelated old topic somewhere in the chat.
    if current and len(current)<=4:return not bool(current & prior & words(reply))
    return not bool(words(reply) & prior)

def unclear_input_reply(language='English'):
    return {'Hindi':'मुझे आपका मतलब साफ़ नहीं समझ आया। क्या आप दोबारा कह सकते हैं?',
            'Hinglish':'Aapka matlab clear nahi hua. Ek baar phir kahoge?'} .get(language,
            "I'm not sure what you meant. Could you say that another way?")
