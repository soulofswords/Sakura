"""Strict spoken grammar for applying one existing model expression in the viewer."""
import re


def request(text):
    value = re.sub(r'\s+', ' ', str(text or '')).strip().rstrip('.!?')
    if not value or len(value) > 140:
        return None
    if re.fullmatch(r'(?:clear|remove|turn off|reset)\s+(?:all\s+)?expressions?|(?:neutral|default)\s+(?:expression|face|look)', value, re.I):
        return {'clear': True, 'label': 'neutral'}
    patterns = (
        r'(?:show|switch|use|change|set)\s+(?:to\s+)?(?:the\s+)?(.+?)\s+(?:expression|face|look|preset)',
        r'(?:show|switch|use|change|set)\s+(?:the\s+)?(?:expression|face|look|preset)\s+(?:to\s+)?(.+)',
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, value, re.I)
        if match:
            label = re.sub(r'^(?:(?:a|an|the|me|my)\s+)+', '', match.group(1).strip(' "\'“”'), flags=re.I)
            # An expression is named, not described: without this, "set volume to 50 and show
            # happy face" reads as one request called "volume to 50 and show happy".
            if len(label.split()) > 4 or re.search(r'[,;]|\b(?:and|then|to|for|with|the)\b', label, re.I):
                continue
            if label and len(label) <= 80:
                return {'clear': False, 'label': label}
    return None


def request_from_speech(text, assistant_name=''):
    """One expression request from a sentence, with or without its polite spoken preamble.

    An expression reaches the avatar only through the reply that answered for it, so a sentence
    that needs speech normalisation ("can you show a happy expression") has to be read here as
    well. Otherwise it falls through to the command table, whose chat entry has no way to hand
    anything to the viewer and can only refuse.
    """
    found = request(text)
    if found:
        return found
    from assistant_commands import normalize
    return request(normalize(text, assistant_name))
