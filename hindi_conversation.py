"""Hindi/Hinglish dialogue instructions and grounded common conversational intents."""
import re

RULES=(
    'Hindi mode: the user can speak Hindi or type Hindi in Latin letters, with spelling variation. '
    'Understand the meaning before answering. Reply in everyday Hindi in Devanagari, usually one or two short sentences. '
    'Do not translate instructions or describe your willingness, consent, quality, seeing questions or providing thoughts. '
    'Answer the actual question. Never repeat a generic invitation in place of an answer. '
    'Examples of intent, not phrases to repeat: "appko hindi ati hai" means "Can you speak Hindi?"; '
    '"aap ladke ho ya ladki" asks about your avatar presentation; "kaise ho" is a friendly greeting. '
    'Use respectful aap. Avoid assuming user gender; prefer "आप कैसे हैं?" over gendered assumptions. '
    'For self-reference follow configured avatar presentation; neutral wording is fine. '
    'Do not invent unrelated metaphors or follow-up questions. If unclear, ask a short clarification in Hindi.')

def common_reply(text,language,presentation='auto'):
    if language not in ('Hindi','Hinglish'):return None
    value=re.sub(r'[?.!।,]+','',text.casefold()).strip()
    value=re.sub(r'\s+',' ',value)
    if re.fullmatch(r'(?:kya )?(?:a+p+ko|tumhe|tumko|aap|tum) hindi (?:a+ti|aati|ati) (?:hai|h|he)|(?:क्या )?(?:आपको|तुम्हें|आप को) (?:हिंदी|हिन्दी) आती है',value):
        return 'हाँ, हम हिंदी में बात कर सकते हैं।' if language=='Hindi' else 'Haan, hum Hindi mein baat kar sakte hain.'
    if re.fullmatch(r'(?:a+p+|tum|aap) (?:kaise|kese|kaisi|kesi) (?:ho|hain|hai)|(?:आप|तुम) (?:कैसे|कैसी) (?:हो|हैं|है)|how are (?:you|u)',value):
        return 'सब बढ़िया! आप कैसे हैं?' if language=='Hindi' else 'Sab badhiya! Aap kaise hain?'
    if re.fullmatch(r'(?:a+p+|tum|aap) (?:ladk[ae]|ladka) ho (?:kya|ya|aur) ladki|(?:आप|तुम) लड़क[ाे] हो (?:या|क्या) लड़की|are you (?:a )?(?:boy or girl|male or female)',value):
        if presentation=='feminine':return 'मेरे अवतार की प्रस्तुति लड़की की है। मैं एक एआई सहायक हूँ।' if language=='Hindi' else 'Mera avatar feminine hai. Main ek AI assistant hoon.'
        if presentation=='masculine':return 'मेरे अवतार की प्रस्तुति लड़के की है। मैं एक एआई सहायक हूँ।' if language=='Hindi' else 'Mera avatar masculine hai. Main ek AI assistant hoon.'
        return 'मैं एक एआई सहायक हूँ। मेरा दिखना आपके चुने हुए अवतार पर निर्भर है।' if language=='Hindi' else 'Main ek AI assistant hoon. Mera look aapke chune hue avatar par depend karta hai.'
    return None

def garbled_reply(text):
    return bool(re.search(r'सरल बातचीत के लिए.*सहमति|मुझे प्रश्न या विचार देखने|सभी देखने के लिए उम्मीद|गुणवत्ता के खेल|के लिए फुल टाइम और स्पष्ट देखना|जब तक आप चाहती हैं|मेरा ज़िक्र है|मेरा जिक्र है',text))
