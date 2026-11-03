"""Remove performed stage directions while preserving actual dialogue."""
import re


def clean_news_for_speech(text):
    """Keep news citations in chat, but speak only the bulletin and headlines."""
    if re.match(r'NVIDIA lists the standard desktop GeForce RTX \d{4} with ', text):
        return text.split('\nSource:', 1)[0].strip()
    if not re.search(r'Recent headlines (?:retrieved now|from Google News):', text):
        return re.sub(r'\nSource:\s*https://\S+\s*$', '', text).strip()
    metadata = re.compile(r'\s*\(([^()\n]{1,80}),\s*\d{4}-\d{2}-\d{2}T[^)\n]*\)\.?\s*Source:\s*https?://\S+')
    output, start = [], 0
    for match in metadata.finditer(text):
        headline = text[start:match.start()]
        headline = re.sub(r'\s*[-–—]\s*' + re.escape(match.group(1)) + r'\s*$', '', headline)
        output.append(headline.rstrip(' .') + '.')
        start = match.end()
    output.append(text[start:])
    text = ''.join(output)
    text = re.sub(r'Recent headlines (?:retrieved now|from Google News):', 'Here are the headlines:', text)
    return re.sub(r'\s+', ' ', text).strip()

ACTION=re.compile(r"^(?:(?:i|she|he|sakura)\s+)?(?:taps?\s+(?:(?:her|his|my|your|the)\s+)?chest|leans?|winks?|smiles?|nods?|adjusts?|giggles?|blush(?:es)?|sighs?|chuckles?|laughs?|tilts?|waves?|clears?\s+(?:her|his|my|the)\s+throat|takes?\s+a\s+bow|sings?|singing|hums?|humming)\b",re.I)


# A small allowlist of expression cues, never executable model-generated code.
EYE_WIDEN = re.compile(r"^(?:(?:her|his|my|sakura['’]s)\s+)?eyes?\s+widen(?:s)?\b(?:\s+(?:slightly|softly|in surprise))?", re.I)
EYE_SPARKLE = re.compile(r"^(?:(?:her|his|my|sakura['’]s)\s+)?eyes?\s+(?:sparkle|twinkle)(?:s)?(?:\s+(?:softly|slightly|with excitement))?$",re.I)
BARE_SPARKLE = re.compile(r"(?:^|(?<=[.!?])\s+)(?:[Ee]yes?\s+(?:[Ss]parkle|[Tt]winkle)(?:s)?)(?:\s+(?:softly|slightly|with excitement))?(?:[ \t]*[.…—–,:;-]+\s*|[ \t]+(?=[A-Z“\"])|[ \t]*$)")

def performance_mood(text):
    prefix=text.lstrip(' *([').strip()
    if BARE_SPARKLE.search(text) or re.search(r'[*(]\s*eyes?\s+(?:sparkle|twinkle)s?(?:\s+(?:softly|slightly|with excitement))?\s*[*\)]',text,re.I):return 'sparkle'
    return 'surprised' if EYE_WIDEN.match(prefix) else None

def clean_performance_markup(text):
    def marked(match):
        inner=match.group(2).strip()
        return '' if ACTION.match(inner) or EYE_WIDEN.fullmatch(inner) or EYE_SPARKLE.fullmatch(inner) else inner
    text=re.sub(r'^\s*(?:[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]\s*)*(?:(?:she|sakura)\s+)?taps?\s+(?:(?:her|his|my|the)\s+)?chest(?:\s+gently)?\s*(?:[.…—–-]+\s*|\n+|$)', '', text, flags=re.I)
    text=re.sub(r'(?<![\w*])(\*{1,2})([^*\s](?:[^*\n]{0,238}[^*\s])?)\1(?![\w*])',marked,text)
    text=re.sub(r'\(([^()\n]{1,160})\)',lambda m:'' if ACTION.match(m.group(1).strip()) or EYE_WIDEN.fullmatch(m.group(1).strip()) or EYE_SPARKLE.fullmatch(m.group(1).strip()) else m.group(0),text)
    text=BARE_SPARKLE.sub(' ',text)
    text=re.sub(r'^\s*(?i:'+EYE_WIDEN.pattern[1:]+r')(?:[ \t]*[.…—–,:;-]+\s*|[ \t]*\n+|[ \t]+(?=[A-Z“\"])|[ \t]*$)', '', text, flags=0)
    return re.sub(r'[ \t]+',' ',text).strip()


# Remove complete emoji sequences before splitting replies into speech phrases.
# Digits remain intact unless they are part of a keycap emoji.
EMOJI=re.compile(
    r'[0-9#*]\ufe0f?\u20e3|'
    r'[\U0001F000-\U0001FAFF\u2600-\u27BF'
    r'\u231A\u231B\u2328\u23CF\u23E9-\u23F3\u23F8-\u23FA'
    r'\u24C2\u25AA\u25AB\u25B6\u25C0\u25FB-\u25FE'
    r'\u2934\u2935\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55'
    r'\u3030\u303D\u3297\u3299\uFE0E\uFE0F\u200D'
    r'\U000E0020-\U000E007F]')

def strip_speech_decoration(text):
    # Internal no-comment signals and visual navigation glyphs are not dialogue.
    text=re.sub(r'\[\s*QUIET\s*\]', '', text, flags=re.I)
    text=re.sub(r'[\u2190-\u21ff\u27f0-\u27ff]+', ' ', text)
    text=EMOJI.sub('',text)
    text=re.sub(r'^\s*>+\s*','',text,flags=re.MULTILINE)
    text=re.sub(r'(?<=\s)>+(?=\s*[“\"\'])','',text)
    return re.sub(r'[ \t]+',' ',text).strip()
