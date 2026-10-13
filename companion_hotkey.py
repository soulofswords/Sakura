"""Shared validated transparency shortcut representation."""
DEFAULT_HOTKEY = 'Ctrl+Shift+T'

def parse_hotkey(value):
    value = value.strip() if isinstance(value, str) else ''
    parts = (value or DEFAULT_HOTKEY).split('+')
    key = parts[-1].upper()
    modifiers = parts[:-1]
    if len(set(modifiers)) != len(modifiers) or any(m not in ('Ctrl','Alt','Shift','Meta') for m in modifiers):
        raise ValueError('Use Ctrl, Alt, Shift or Meta with a letter, number or F1–F12.')
    if len(key)==1 and key.isascii() and key.isalnum(): vk=ord(key)
    elif key.startswith('F') and key[1:].isdigit() and 1<=int(key[1:])<=12: vk=0x70+int(key[1:])-1
    else: raise ValueError('Choose a letter, number or F1–F12.')
    if not any(m in modifiers for m in ('Ctrl','Alt','Meta')):
        raise ValueError('Include Ctrl, Alt or Meta to avoid interfering with typing.')
    canonical = '+'.join([m for m in ('Ctrl','Alt','Shift','Meta') if m in modifiers]+[key])
    if canonical=='Ctrl+Shift+H': raise ValueError('Ctrl+Shift+H is reserved for hiding controls.')
    flags=sum({'Alt':1,'Ctrl':2,'Shift':4,'Meta':8}[m] for m in modifiers)
    mac='+'.join([{'Ctrl':'<ctrl>','Alt':'<alt>','Shift':'<shift>','Meta':'<cmd>'}[m] for m in ('Ctrl','Alt','Shift','Meta') if m in modifiers]+[('<'+key.lower()+'>') if len(key)>1 else key.lower()])
    return canonical,flags,vk,mac
