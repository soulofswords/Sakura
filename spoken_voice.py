"""Resolve a spoken or typed voice name to one real selectable voice, or explain why it could not."""
import re

from voice_catalog import VOICE_ALIASES, VOICE_PRESETS


def _words(value):
    return [word for word in re.split(r'[^a-z0-9]+', str(value or '').casefold()) if word]


# Speech surrounds the name with the request itself: “switch to the Bella voice please”.
_FILLER = {'a', 'an', 'and', 'for', 'i', 'in', 'is', 'm', 'my', 'now', 'of', 'please', 's', 'set', 'speaker',
           'switch', 'the', 'to', 'tone', 'u', 'use', 'using', 'voice', 'voices', 'want', 'with', 'you'}


def _vocab(*values):
    return set().union(*(_words(value) for value in values))


def _forms(*values):
    """Full name spellings as token runs, so “af puck” has to arrive as those two words in order."""
    return [words for words in (_words(value) for value in values) if words]


def _run_inside(tokens, run):
    return any(tokens[start:start + len(run)] == run for start in range(len(tokens) - len(run) + 1))


_windows = None


def windows_voices(refresh=False):
    """Windows' own offline voices. That search takes about a second, so ask for it once per session."""
    global _windows
    if _windows is None or refresh:
        try:
            from system_speech import system_voice_presets
            _windows = system_voice_presets()
        except (ImportError, OSError, ValueError):
            _windows = []
    return _windows


def selectable(presets=None, system=None):
    """Every voice the app can switch to, one record per id, with the old names folded in."""
    # None asks Windows; [] means the caller already knows there are no offline voices.
    system = windows_voices() if system is None else list(system)
    records = {}
    for preset in list(presets if presets is not None else VOICE_PRESETS) + system:
        records[preset['id']] = {'id': preset['id'], 'name': preset['name'],
                                 'words': _vocab(preset['name'], preset.get('voice', ''),
                                                 preset.get('language', ''), preset.get('gender', ''),
                                                 preset.get('desc', '')),
                                 'forms': _forms(preset['name'], preset.get('voice', ''))}
    for alias, target in VOICE_ALIASES.items():
        record = records.get(target)
        if record is not None:
            # Legacy Edge and pre-Kokoro names keep working without becoming a second voice.
            record['words'] |= _vocab(alias)
            record['forms'] += _forms(alias)
    return list(records.values())


def _matches(label, presets=None, system=None):
    """Voices a spoken label could mean, best score first. Empty when nothing came close."""
    wanted = str(label or '').strip().rstrip('.!?').strip()
    if not wanted or len(wanted) > 60:
        return []
    tokens = [word for word in _words(wanted) if word not in _FILLER]
    if not tokens:
        return []
    records = selectable(presets, system)
    exact = [item for item in records
             if wanted.casefold() in (str(item['id']).casefold(), str(item['name']).casefold())]
    if len({item['id'] for item in exact}) == 1:
        return [{'item': exact[0], 'score': 100}]
    # “the Hindi voice”, “a male voice”, “Sakura's heart” all have to survive normal speech.
    scored = []
    for item in records:
        if any(_run_inside(tokens, run) for run in item['forms']):
            scored.append({'item': item, 'score': 100})
        elif all(word in item['words'] for word in tokens):
            scored.append({'item': item, 'score': len(tokens) * 3})
        else:
            shared = len(set(tokens) & item['words'])
            if shared:
                scored.append({'item': item, 'score': shared})
    scored.sort(key=lambda entry: -entry['score'])
    return scored


def resolve(label, presets=None, system=None):
    """One voice only. Returns it, or raises with the choices that were close."""
    wanted = str(label or '').strip().rstrip('.!?').strip()
    if not wanted:
        raise ValueError('Tell me which voice to use.')
    if len(wanted) > 60:
        raise ValueError('Name one voice, not a whole sentence.')
    scored = _matches(wanted, presets, system)
    if not scored:
        if not [word for word in _words(wanted) if word not in _FILLER]:
            raise ValueError('Name the voice you want.')
        raise ValueError(f'I have no voice called “{wanted}”. Ask “what voices do I have” to see what is installed.')
    best = scored[0]['score']
    top = [entry for entry in scored if entry['score'] == best]
    if len({entry['item']['id'] for entry in top}) == 1:
        return top[0]['item']
    names = sorted({entry['item']['name'] for entry in top}, key=str.casefold)[:4]
    joined = ' or '.join('“' + name + '”' for name in names)
    if len(top) > 4:
        raise ValueError(f'“{wanted}” matches several voices, starting with {joined}. Name one of them.')
    raise ValueError(f'“{wanted}” matches {joined}. Name one of them.')


# “switch to Bella”, “use the Bella voice”, “talk like Puck” — and nothing that is not about voices.
_LIST = re.compile(r'(?:^(?:what|which)\s+voices?\s+(?:do\s+(?:i|we)\s+have|are\s+(?:there|available|installed|here)'
                   r'|can\s+i\s+(?:use|choose|pick|hear))|^(?:list|show|tell me)\s+(?:me\s+)?'
                   r'(?:the\s+|available\s+|all\s+)*voices|^(?:voice|persona)\s*(?:list|options|choices)'
                   r'|^what\s+(?:other\s+)?(?:voices|tones)\s+can\s+(?:you|ur)\s+(?:use|do|sound\s+like))', re.I)
_SWITCH = re.compile(r'^(?:(?:switch|change|convert|set|move)(?:\s+(?:your|the|to|back|now|voice|persona|preset))*\s+to'
                     r'|(?:voice|persona)\s+to|(?:talk|speak|sound)\s+like)\s+'
                     r'(?:the\s+|your\s+)*(.{1,60}?)(?:\s+(?:voice|persona|tone|speaker))?'
                     r'(?:\s+(?:from\s+now\s+on|instead|now|right\s+away))?$', re.I)
_USE = re.compile(r'^use\s+(?:the\s+|your\s+)*(.{1,60}?)\s+(?:voice|persona|tone|speaker)$', re.I)
_ABOUT_VOICES = re.compile(r'\b(?:voices?|personas?|tones?|speakers?|audio)\b', re.I)


def request(text):
    """The voice change asked for in this sentence: {'show':True}, {'label':…}, or None."""
    sentence = str(text or '').strip().lower().rstrip('.!?').strip()
    if not sentence:
        return None
    if _LIST.fullmatch(sentence):
        return {'show': True}
    match = _USE.fullmatch(sentence) or _SWITCH.fullmatch(sentence)
    if not match:
        return None
    label = match.group(1).strip()
    if not label:
        return None
    # Only claim “switch to …” when it names a voice, so a theme or window request stays free.
    if not _ABOUT_VOICES.search(sentence) and not _matches(label):
        return None
    return {'label': label}


def summary(system=None):
    """What Sakura can answer when asked which voices exist."""
    records = selectable(system=system)
    names = sorted({record['name'] for record in records}, key=str.casefold)
    shown = ', '.join(names[:12])
    more = f', and {len(names) - 12} more' if len(names) > 12 else ''
    return f'I can sound like {shown}{more}. Say “switch to” and name one to change my voice.'

