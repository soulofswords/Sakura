"""Deterministic everyday commands, without waiting for model generation."""
import re
import webbrowser
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from urllib.parse import quote_plus


def run_command(text, computer_access=False, assistant_name="Sakura"):
    command = re.sub(r"\s+", " ", text.lower()).strip().rstrip('.!?')
    command = re.sub(r'\bu\b', 'you', command)
    name = re.escape(str(assistant_name).lower().strip() or 'sakura')
    command = re.sub(rf'^(?:hey[,!. ]+)?{name}[,!. ]+', '', command)
    command = re.sub(r'^hey[,!. ]+(?=(?:can|could|would|please|open|launch|start)\b)', '', command)
    command = re.sub(r'(?:[, ]+(?:for me|please))+$', '', command).strip()
    # Speech often includes an acknowledgement, the assistant's name, or a
    # polite lead-in before the actual command. Strip only anchored prefixes.
    for _ in range(4):
        previous = command
        command = re.sub(r'^(?:(?:ok(?:ay)?|alright)(?: then)?|(?:hey )?sakura)[,!. ]+', '', command)
        command = re.sub(r'^(?:please|(?:what )?(?:can|could|would) you(?: please)?|i want you to)[, ]+', '', command)
        if command == previous:
            break
    command = re.sub(r'[, ]+please$', '', command).strip().rstrip('.!?')
    command = re.sub(r'\byou tube\b', 'youtube', command)
    from steam_commands import run_steam_command
    steam_reply = run_steam_command(command, computer_access)
    if steam_reply is not None:
        return steam_reply
    browser_names = {'chrome': ('Google Chrome', 'Google/Chrome/Application/chrome.exe'),
                     'edge': ('Microsoft Edge', 'Microsoft/Edge/Application/msedge.exe')}
    browser_match = re.fullmatch(r'(?:open|launch|start) (?:(?:google|microsoft) )?(chrome|edge)(?: browser)?', command)
    if browser_match:
        browser = browser_match.group(1)
        label, relative = browser_names[browser]
        if not computer_access:
            return f'Enable computer access in Settings first, and I can open {label} for you.'
        if sys.platform == 'darwin':
            app_path = next((root / (label + '.app') for root in (Path('/Applications'), Path.home() / 'Applications')
                             if (root / (label + '.app')).is_dir()), None)
            if app_path is None:
                return f"I couldn't find {label} installed on this computer."
            try:
                subprocess.Popen(['/usr/bin/open', '-a', str(app_path), 'https://www.google.com'], shell=False)
                return f'Opening {label}.'
            except OSError:
                return f"I couldn't start {label}. Try opening it manually once."
        candidates = [Path(os.environ.get('PROGRAMFILES', r'C:\Program Files')) / relative,
                      Path(os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)')) / relative,
                      Path(os.environ.get('LOCALAPPDATA', '')) / relative]
        executable = next((path for path in candidates if path.is_file()), None)
        if not executable:
            return f"I couldn't find {label} installed on this computer."
        try:
            subprocess.Popen([str(executable), '--new-window', 'https://www.google.com'], shell=False)
            return f'Opening {label}.'
        except OSError:
            return f"I couldn't start {label}. Try opening it manually once."
    if command in {'what time is it', "what's the time", 'tell me the time', 'time'}:
        return f"It's {datetime.now().strftime('%I:%M %p').lstrip('0')}."
    if command in {"what's the date", 'what is the date', "what is today's date", 'what day is it', 'tell me the date'}:
        return f"Today is {datetime.now().strftime('%A, %d %B %Y')}."
    sites = {'youtube': ('YouTube', 'https://www.youtube.com'),
             'google': ('Google', 'https://www.google.com'),
             'github': ('GitHub', 'https://github.com'),
             'twitch': ('Twitch', 'https://www.twitch.tv')}
    target = None
    label = None
    for name, (display, url) in sites.items():
        if command in {f'open {name}', f'launch {name}', f'go to {name}', f'start {name}'}:
            target, label = url, display
            break
    if command in {'search', 'do a search', 'search something', 'search google', 'search youtube'}:
        return 'What would you like me to search for?'
    youtube = re.fullmatch(r'(?:search youtube(?: for)?|find on youtube) (.+)', command)
    if not youtube:
        youtube = re.fullmatch(r'(?:search(?: for)?|find) (.+?) on youtube', command)
    if not youtube:
        youtube = re.fullmatch(r'open youtube and search(?: for)? (.+)', command)
    search = None if youtube else re.fullmatch(r'(?:search(?: (?:google|the web))?(?: for)?|google) (.+)', command)
    if search:
        target = 'https://www.google.com/search?q=' + quote_plus(search.group(1))
        label = 'Google search'
    elif youtube:
        target = 'https://www.youtube.com/results?search_query=' + quote_plus(youtube.group(1))
        label = 'YouTube search'
    if target:
        if not computer_access:
            return 'Enable computer access in Settings first, and I can open that for you.'
        return f'Opening {label}.' if webbrowser.open(target, new=2) else f"I couldn't open {label} in your browser."
    return None
