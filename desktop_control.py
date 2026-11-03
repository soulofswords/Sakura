"""Voice-reachable desktop input on Windows, synthesised with SendInput. Always reviewable first."""
import ctypes
import re
import sys
import time

_IS_WINDOWS = sys.platform == 'win32'

_LEAD = (r'^(?:(?:hey|ok(?:ay)?|alright|so|then)[,!. ]+)*'
         r'(?:(?:sakura|assistant)[,!. ]+)*'
         r'(?:(?:please|kindly|can (?:you|u)|could (?:you|u)|would (?:you|u)|'
         r'i want (?:you|u) to|go ahead and|try to)[,!. ]+)*')

_KEYS = {
    'ctrl': 0x11, 'control': 0x11, 'alt': 0x12, 'shift': 0x10, 'win': 0x5B, 'windows': 0x5B,
    'enter': 0x0D, 'return': 0x0D, 'tab': 0x09, 'esc': 0x1B, 'escape': 0x1B, 'space': 0x20,
    'backspace': 0x08, 'delete': 0x2E, 'del': 0x2E, 'insert': 0x2D, 'home': 0x24, 'end': 0x23,
    'pageup': 0x21, 'pgup': 0x21, 'pagedown': 0x22, 'pgdn': 0x22,
    'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27, 'capslock': 0x14,
    'printscreen': 0x2C, 'pause': 0x13, 'menu': 0x5D,
    'period': 0xBE, 'dot': 0xBE, 'comma': 0xBC, 'slash': 0xBF, 'semicolon': 0xBA,
    'apostrophe': 0xDE, 'minus': 0xBD, 'dash': 0xBD, 'equals': 0xBB,
    'playpause': 0xB3, 'media_play_pause': 0xB3,
    'nexttrack': 0xB0, 'media_next': 0xB0,
    'prevtrack': 0xB1, 'media_previous': 0xB1,
    'stop': 0xB2, 'media_stop': 0xB2,
    'volumemute': 0xAD, 'media_mute': 0xAD,
    'volumeup': 0xAF, 'media_volume_up': 0xAF,
    'volumedown': 0xAE, 'media_volume_down': 0xAE,
}
_KEYS.update({f'f{number}': 0x6F + number for number in range(1, 25)})

_MOUSE_MOVE, _MOUSE_LEFT_DOWN, _MOUSE_LEFT_UP = 0x0001, 0x0002, 0x0004
_MOUSE_RIGHT_DOWN, _MOUSE_RIGHT_UP = 0x0008, 0x0010
_MOUSE_WHEEL, _MOUSE_ABSOLUTE = 0x0800, 0x8000
_KEY_UP, _KEY_UNICODE = 0x0002, 0x0004
_WHEEL_DELTA = 120
_GA_ROOT = 2
_BUTTONS = {'left': (_MOUSE_LEFT_DOWN, _MOUSE_LEFT_UP), 'right': (_MOUSE_RIGHT_DOWN, _MOUSE_RIGHT_UP)}
# “click at 9, 9 then …” has to be watched too, so a request splits the way the runner splits it.
_SEQUENCE = re.compile(r'\s*(?:,?\s+(?:and )?then\s+|;\s*)', re.I)

_target = {'hwnd': 0, 'point': None}

# “click on the” and “click on it” are half-spent sentences, not control names.
_STOPWORDS = {'a', 'an', 'the', 'this', 'that', 'these', 'those', 'it', 'there', 'here',
              'one', 'them', 'on', 'in', 'to', 'at', 'my', 'your', 'his', 'some'}


def _token_of(word):
    return ''.join(character for character in word.casefold() if character.isalnum())


def _is_stopwords(label):
    return all(_token_of(word) in _STOPWORDS or not _token_of(word)
               for word in re.split(r'[\s,]+', label))


def available():
    return _IS_WINDOWS


def mark_target(text=''):
    """Remember the window the user was using, so an approved action returns to it instead of Sakura."""
    _target['hwnd'] = 0
    _target['point'] = None
    if not _IS_WINDOWS:
        return
    try:
        _target['hwnd'] = ctypes.windll.user32.GetForegroundWindow() or 0
    except Exception:
        _target['hwnd'] = 0
    for piece in _SEQUENCE.split(str(text or '')):
        command = parse_command(piece)
        if command and command['action'] == 'desktop.click':
            x, y = command['arguments']['x'], command['arguments']['y']
            try:
                root = _root_under(x, y)
            except ValueError:
                root = None
            _target['point'] = {'x': x, 'y': y, 'root': root}
            break


# Windows treats media keys globally, so they bypass the focused-window path entirely.
_MEDIA_PHRASES = {'play pause': 'playpause', 'next track': 'nexttrack', 'skip track': 'nexttrack',
                  'prev track': 'prevtrack', 'previous track': 'prevtrack', 'stop': 'stop',
                  'volume mute': 'volumemute', 'volume up': 'volumeup', 'volume down': 'volumedown'}
# "playpause", "play_pause" and "play pause" are the same request.
_MEDIA_KEYS = {phrase.replace(' ', ''): key for phrase, key in _MEDIA_PHRASES.items()}
_MEDIA = re.compile(_LEAD + r'(?:press|hit)\s+(?:the\s+)?(?:media\s+)?(?:key\s+)?(' + '|'.join(
    r'[ _]?'.join(re.escape(word) for word in phrase.split())
    for phrase in sorted(_MEDIA_PHRASES, key=len, reverse=True)) +
    r')(?:\s+(?:key|button))?$', re.I)
_DIRECT_MEDIA_PHRASES = {'play pause': 'playpause', 'pause music': 'playpause', 'resume music': 'playpause',
                         'next track': 'nexttrack', 'skip track': 'nexttrack',
                         'previous track': 'prevtrack', 'prev track': 'prevtrack', 'last track': 'prevtrack',
                         'stop playback': 'stop', 'stop music': 'stop'}
_DIRECT_MEDIA = re.compile(_LEAD + r'(' + '|'.join(
    r'\s+'.join(re.escape(word) for word in phrase.split())
    for phrase in sorted(_DIRECT_MEDIA_PHRASES, key=len, reverse=True)) + r')$', re.I)


def parse_media(text):
    """A media-key request, returned as the canonical key media_press understands."""
    value = re.sub(r'\s+', ' ', str(text or '')).strip().rstrip('.!?')
    match = _MEDIA.fullmatch(value)
    if match:
        return _MEDIA_KEYS.get(re.sub(r'[ _]+', '', match[1].casefold()))
    match = _DIRECT_MEDIA.fullmatch(value)
    return _DIRECT_MEDIA_PHRASES.get(re.sub(r'\s+', ' ', match[1].casefold())) if match else None


def parse_command(text):
    """One strict voice grammar for clicks, typing, keys and scrolling. None when it is not one."""
    value = re.sub(r'\s+', ' ', str(text or '')).strip().rstrip('.!?')
    if not value or len(value) > 520:
        return None
    match = re.match(_LEAD + r'((?:double|right)[-_ ])?click\s+(?:(?:at|on)\s+)?(\d{1,4})\s*[, ]\s*(\d{1,4})$', value, re.I)
    if match:
        kind = (match[1] or '').casefold().replace('-', ' ').strip()
        return {'action': 'desktop.click',
                'arguments': {'x': int(match[2]), 'y': int(match[3]),
                              'button': 'right' if 'right' in kind else 'left',
                              'times': 2 if 'double' in kind else 1}}
    match = re.match(_LEAD + r'((?:double|right)[-_ ])?click\s+(?:on\s+)?(?:the\s+)?(.+)$', value, re.I)
    if match:
        label = match[2].strip()
        trimmed = re.sub(r'\s+(?:button|link|icon|tab|menu item|option)$', '', label, flags=re.I).strip()
        if trimmed:
            label = trimmed
        label = label.strip('"\'“”').strip()
        if not label or len(label) > 60 or _is_stopwords(label):
            return None
        kind = (match[1] or '').casefold().replace('-', ' ').strip()
        return {'action': 'desktop.click_text',
                'arguments': {'label': label, 'button': 'right' if 'right' in kind else 'left',
                              'times': 2 if 'double' in kind else 1}}
    match = re.match(_LEAD + r'type(?:\s+this)?\s*:?\s+(.+)$', value, re.I)
    if match and match[1].strip():
        if len(match[1]) > 500 or re.match(r'(?:of|is|are)\b', match[1].strip(), re.I):
            return None
        return {'action': 'desktop.type', 'arguments': {'text': match[1]}}
    match = re.match(_LEAD + r'(?:press|hit)\s+(?:the\s+)?(.+)$', value, re.I)
    if match:
        combo = re.sub(r'\s+keys?$', '', match[1].strip(), flags=re.I)
        try:
            _key_codes(combo)
        except ValueError:
            return None
        return {'action': 'desktop.press', 'arguments': {'combo': combo}}
    match = re.match(_LEAD + r'scroll\s+(up|down)(?:\s+(a ?bit|a ?little|a ?lot|by\s+\d{1,2}))?$', value, re.I)
    if match:
        amount = 3
        modifier = (match[2] or '').lower().replace(' ', '')
        if modifier in ('abit', 'alittle'):
            amount = 1
        elif modifier == 'alot':
            amount = 6
        elif modifier.startswith('by'):
            amount = max(1, min(10, int(re.search(r'\d+', modifier).group())))
        return {'action': 'desktop.scroll', 'arguments': {'direction': match[1].lower(), 'amount': amount}}
    return None


def needs_review(text):
    return parse_command(text) is not None


def _key_codes(combo):
    value = re.sub(r'\s+plus\s+', '+', str(combo).strip(), flags=re.I)
    value = re.sub(r'\bpage up\b', 'pageup', value, flags=re.I)
    value = re.sub(r'\bpage down\b', 'pagedown', value, flags=re.I)
    value = re.sub(r'\barrow (up|down|left|right)\b', r'\1', value, flags=re.I)
    parts = [part for part in re.split(r'\s*\+\s*|\s+', value) if part]
    if not parts or len(parts) > 4:
        raise ValueError('Use up to four keys, for example ctrl plus s.')
    codes = []
    for part in parts:
        key = part.lower()
        if key in _KEYS:
            codes.append(_KEYS[key])
        elif re.fullmatch(r'[a-z]', key):
            codes.append(ord(key.upper()))
        elif re.fullmatch(r'[0-9]', key):
            codes.append(ord(key))
        else:
            raise ValueError('I do not know the key ' + part + '.')
    return codes


class _POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', ctypes.c_long), ('dy', ctypes.c_long), ('mouseData', ctypes.c_ulong),
                ('dwFlags', ctypes.c_ulong), ('time', ctypes.c_ulong), ('dwExtraInfo', ctypes.c_size_t)]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', ctypes.c_ushort), ('wScan', ctypes.c_ushort), ('dwFlags', ctypes.c_ulong),
                ('time', ctypes.c_ulong), ('dwExtraInfo', ctypes.c_size_t)]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [('uMsg', ctypes.c_ulong), ('wParamL', ctypes.c_ushort), ('wParamH', ctypes.c_ushort)]


class _INPUT(ctypes.Structure):
    class _Union(ctypes.Union):
        _fields_ = [('mi', _MOUSEINPUT), ('ki', _KEYBDINPUT), ('hi', _HARDWAREINPUT)]
    _anonymous_ = ('u',)
    _fields_ = [('type', ctypes.c_ulong), ('u', _Union)]


def _send(*events):
    if not _IS_WINDOWS:
        raise OSError('Desktop input is available on Windows only.')
    array = (_INPUT * len(events))(*events)
    sent = ctypes.windll.user32.SendInput(len(events), array, ctypes.sizeof(_INPUT))
    if sent != len(events):
        raise OSError('Windows did not accept that input. Nothing else was sent.')


def _mouse(flags, dx=0, dy=0, data=0):
    event = _INPUT(type=0)
    event.mi = _MOUSEINPUT(dx=dx, dy=dy, mouseData=data, dwFlags=flags, time=0, dwExtraInfo=0)
    return event


def _key(vk, flags=0, scan=0):
    event = _INPUT(type=1)
    event.ki = _KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    return event


def screen_size():
    if not _IS_WINDOWS:
        raise OSError('Desktop input is available on Windows only.')
    return ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)


def _root_under(x, y):
    """The top-level window owning these pixels. Handles are 64-bit, so give ctypes their real width."""
    if not _IS_WINDOWS:
        return 0
    user32 = ctypes.windll.user32
    try:
        user32.WindowFromPoint.restype = ctypes.c_void_p
        user32.WindowFromPoint.argtypes = [_POINT]
        user32.GetAncestor.restype = ctypes.c_void_p
        user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        handle = user32.WindowFromPoint(_POINT(int(x), int(y)))
        return (user32.GetAncestor(handle, _GA_ROOT) if handle else 0) or 0
    except Exception:
        raise ValueError('I could not check which window owns that point, so nothing was clicked.')


def _guard_point(x, y):
    """A typed-in coordinate follows the screen, not your intent, so refuse if the window moved away."""
    watched = _target.get('point')
    if not watched or (int(watched['x']), int(watched['y'])) != (int(x), int(y)):
        return
    if _root_under(x, y) != watched['root']:
        raise ValueError('A different window is now where you asked me to click, so nothing was clicked.')


def click(x, y, button='left', times=1):
    x, y = int(x), int(y)
    try:
        press_flag, release_flag = _BUTTONS[str(button or 'left')]
    except KeyError:
        raise ValueError('I can only click with the left or right button.')
    width, height = screen_size()
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError('That point is outside this screen. Nothing was clicked.')
    _guard_point(x, y)
    _send(_mouse(_MOUSE_MOVE | _MOUSE_ABSOLUTE,
                 int(round(x * 65535 / max(1, width - 1))), int(round(y * 65535 / max(1, height - 1)))))
    for _ in range(max(1, min(2, int(times or 1)))):
        _send(_mouse(press_flag), _mouse(release_flag))
        time.sleep(0.04)


def type_text(text):
    text = str(text or '')
    if not text.strip():
        raise ValueError('Tell me what to type.')
    if len(text) > 500:
        raise ValueError('I can type at most 500 characters at once.')
    if any(ord(character) < 32 for character in text):
        raise ValueError('I can only type plain text, without newlines or control characters.')
    _ensure_target()
    events = []
    data = text.encode('utf-16-le')
    for index in range(0, len(data), 2):
        scan = data[index] | (data[index + 1] << 8)
        events.append(_key(0, _KEY_UNICODE, scan))
        events.append(_key(0, _KEY_UNICODE | _KEY_UP, scan))
    _send(*events)


def press(combo):
    codes = _key_codes(combo)
    _ensure_target()
    events = [_key(code) for code in codes] + [_key(code, _KEY_UP) for code in reversed(codes)]
    _send(*events)


def media_press(key):
    """Press a media key globally (no target window needed). Works on Windows only."""
    if not _IS_WINDOWS:
        raise OSError('Media keys are available on Windows only.')
    value = key.strip().lower()
    code = _KEYS.get(value)
    if code is None:
        # Also accept a raw virtual-key code as an integer string
        try:
            code = int(value, 0)
        except ValueError:
            raise ValueError('I do not know that media key. Try playpause, nexttrack, prevtrack, stop, volumemute, volumeup, or volumedown.')
    _send(_key(code), _key(code, _KEY_UP))


def scroll(direction, amount=3):
    if direction not in ('up', 'down'):
        raise ValueError('Scroll up or down.')
    amount = max(1, min(10, int(amount)))
    # Windows sends the wheel to the window under the pointer, so the pointer is left
    # exactly where the user put it and only the wheel event is synthesised.
    _send(_mouse(_MOUSE_WHEEL, data=(_WHEEL_DELTA * amount) if direction == 'up' else -(_WHEEL_DELTA * amount)))


def _ensure_target():
    """Approving in Sakura moves focus; return it to the window the request came from."""
    hwnd = _target.get('hwnd') or 0
    if not hwnd:
        return
    try:
        user32 = ctypes.windll.user32
        if not user32.IsWindow(hwnd):
            _target['hwnd'] = 0
            return
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.2)
        if user32.GetForegroundWindow() != hwnd:
            raise ValueError('I could not return focus to the window you were using, so I did not type or press anything.')
    except ValueError:
        raise
    except Exception:
        raise ValueError('I could not return focus to the window you were using, so I did not type or press anything.')


def execute_action(action, arguments):
    if not _IS_WINDOWS:
        return {'ok': False, 'reply': 'Desktop input is available on Windows only.', 'data': {}}
    try:
        if action == 'desktop.click':
            x, y = int(arguments.get('x')), int(arguments.get('y'))
            button, times = arguments.get('button', 'left'), int(arguments.get('times') or 1)
            click(x, y, button, times)
            return {'ok': True, 'reply': f"{_click_word(button, times)} at {x}, {y}.", 'data': {'x': x, 'y': y}}
        if action == 'desktop.click_text':
            return _click_text(str(arguments.get('label') or '').strip(),
                               arguments.get('button', 'left'), int(arguments.get('times') or 1))
        if action == 'desktop.type':
            text = str(arguments.get('text') or '')
            type_text(text)
            return {'ok': True, 'reply': f'Typed {len(text)} characters into the focused window.',
                    'data': {'characters': len(text)}}
        if action == 'desktop.press':
            combo = str(arguments.get('combo') or '')
            press(combo)
            return {'ok': True, 'reply': f'Pressed {combo}.', 'data': {'combo': combo}}
        if action == 'desktop.scroll':
            direction, amount = arguments.get('direction'), arguments.get('amount', 3)
            scroll(direction, amount)
            return {'ok': True, 'reply': f'Scrolled {direction}.', 'data': {'direction': direction, 'amount': amount}}
        if action == 'media.press':
            key = str(arguments.get('key') or '')
            media_press(key)
            return {'ok': True, 'reply': f'Pressed {key}.', 'data': {'key': key}}
        raise ValueError('Unsupported desktop action.')
    except (ValueError, OSError, TypeError) as error:
        return {'ok': False, 'reply': str(error), 'data': {}}


def _click_word(button, times):
    if button == 'right':
        return 'Right-clicked'
    return 'Double-clicked' if int(times or 1) > 1 else 'Clicked'


def _click_text(label, button='left', times=1):
    if not label:
        return {'ok': False, 'reply': 'Tell me which word or button to click.', 'data': {}}
    import ocr
    if not ocr.engine_name():
        return {'ok': False, 'reply': 'Windows OCR is not available, so I cannot find that label on screen. '
                                      'Try “click at” with a position instead.', 'data': {}}
    from io import BytesIO
    from PIL import ImageGrab
    shot = ImageGrab.grab()
    buffer = BytesIO()
    shot.save(buffer, format='PNG')
    try:
        matches = ocr.locate(label, buffer.getvalue(), '.png')
    except ValueError as error:
        return {'ok': False, 'reply': str(error), 'data': {'label': label}}
    if not matches:
        return {'ok': False, 'reply': f'I could not find “{label}” on this screen. Nothing was clicked.',
                'data': {'label': label, 'matches': 0}}
    best = matches[0]
    if best['score'] < 3 and len(matches) > 1:
        words = ', '.join(f'“{item["text"]}”' for item in matches[:3])
        return {'ok': False, 'reply': f'More than one thing on screen looks like “{label}”: {words}. '
                                      'Name the exact word or use “click at” with a position. Nothing was clicked.',
                'data': {'label': label, 'matches': len(matches)}}
    width, height = screen_size()
    scale_x, scale_y = width / shot.width, height / shot.height
    x = int(round((best['x'] + best['width'] / 2) * scale_x))
    y = int(round((best['y'] + best['height'] / 2) * scale_y))
    click(x, y, button, times)
    note = f' ({len(matches)} matches; clicked the first)' if len(matches) > 1 else ''
    return {'ok': True, 'reply': f'{_click_word(button, times)} “{best["text"]}”{note}.',
            'data': {'label': label, 'clicked': best['text'], 'x': x, 'y': y, 'matches': len(matches)}}
