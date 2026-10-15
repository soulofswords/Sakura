"""Remove performed stage directions while preserving actual dialogue."""
import re

ACTION=re.compile(r"^(?:(?:i|she|he|sakura)\s+)?(?:leans?|winks?|smiles?|nods?|adjusts?|giggles?|blush(?:es)?|sighs?|chuckles?|laughs?|tilts?|waves?|clears?\s+(?:her|his|my|the)\s+throat|takes?\s+a\s+bow|sings?|singing|hums?|humming)\b",re.I)


def clean_performance_markup(text):
    def marked(match):
        inner=match.group(2).strip()
        return '' if ACTION.match(inner) else inner
    text=re.sub(r'(?<![\w*])(\*{1,2})([^*\s](?:[^*\n]{0,238}[^*\s])?)\1(?![\w*])',marked,text)
    text=re.sub(r'\(([^()\n]{1,160})\)',lambda m:'' if ACTION.match(m.group(1).strip()) else m.group(0),text)
    return re.sub(r'[ \t]+',' ',text).strip()
