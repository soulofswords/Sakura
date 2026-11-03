"""A rendering protocol, never a computer/tool permission or arbitrary code."""
import re

ACTIONS = ('home', 'desk', 'mirror', 'bed', 'nod', 'shake_head', 'stretch')
TOKEN = re.compile(r'\[\[avatar:([^\]\r\n]{0,100})\]\]', re.I)
PROTOCOL = 'Sakura room animation protocol'


def instruction(capabilities):
    if not isinstance(capabilities, list):
        return ''
    allowed = [name for name in ACTIONS if name in capabilities]
    if not allowed:
        return ''
    return (PROTOCOL + ': the user enabled control of your virtual body and a simple room or marked furniture points on an imported PMX stage. '
            'You may append at most ONE [[avatar:ACTION]] to your reply, choosing only from '
            + ', '.join(allowed) + '. Prefer no action when unnecessary. home returns to your original place; '
            'desk walks to a virtual desk and mimes typing; mirror walks to a mirror; bed walks to a bed and lies down; '
            'nod, shake_head and stretch are brief poses. These are virtual animations, not real computer actions. '
            'Never claim an animation has finished, deleted a file or operated an actual app. '
            'Keep answering naturally; never speak the token. Do not replace a hello/greeting wave.')


def extract(reply):
    """Strip all complete control tokens, admitting only one exact known action."""
    if not isinstance(reply, str):
        return reply, None
    tokens = TOKEN.findall(reply)
    action = tokens[0].strip().lower() if len(tokens) == 1 else None
    return TOKEN.sub('', reply).strip(), action if action in ACTIONS else None


def requested_action(text):
    """Direct virtual-room requests work even with models that omit the token."""
    value=re.sub(r'^(?:(?:sakura|please)[, ]+|(?:can|could|would) you )+', '', str(text).strip().lower()).rstrip('.!? ')
    commands={
        'desk': ('go to the desk','walk to the desk','use the virtual desk','type at the desk'),
        'mirror': ('go to the mirror','walk to the mirror','look in the mirror'),
        'bed': ('go to bed','go to the bed','lie on the bed','lie down on the bed','go to sleep','you can sleep now','u can sleep now','you can go to sleep','you can rest now','take a nap','get some rest','time to sleep','सो जाओ','so jao'),
        'home': ('come back','come back here','return home','return to your place','wake up sakura','sakura wake up','wake up','get out of bed','get up sakura'),
        'nod': ('nod','nod your head'), 'shake_head': ('shake your head',),
        'stretch': ('stretch','stretch your arms'),
    }
    return next((action for action,phrases in commands.items() if value in phrases),None)
