"""Deterministic everyday commands, without waiting for model generation."""
import re
import webbrowser
import os
import subprocess
import sys
import json
from pathlib import Path
from urllib.parse import quote_plus


def normalize(text, assistant_name="Sakura"):
    """Speech/name cleanup shared by command routing and background sequences."""
    command = re.sub(r"\s+", " ", text.lower().replace("’", "'")).strip().rstrip('.!?')
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
    return re.sub(r'\byou tube\b', 'youtube', command)


def background_sequence(text, computer_access=False, assistant_name="Sakura", channel="desktop"):
    """Start an explicit multi-step sequence without blocking the reply. None when it is not one."""
    from assistant_tools import start_sequence
    return start_sequence(normalize(text, assistant_name), computer_access, assistant_name, channel)


def run_command(text, computer_access=False, assistant_name="Sakura", channel="desktop"):
    from assistant_reminders import reminders
    command = normalize(text, assistant_name)
    from calendar_chat import calendar_command
    calendar_reply=calendar_command(command,channel)
    if calendar_reply is not None:return calendar_reply
    # Use the same speech/name normalization for local utilities as app commands.
    from assistant_tools import handle_command
    tool_reply=handle_command(command,computer_access,assistant_name,channel)
    if tool_reply is not None:return tool_reply
    reminder_reply = reminders.command(command)
    if reminder_reply is not None:
        return reminder_reply
    from local_clock import clock_command
    clock_reply=clock_command(command)
    if clock_reply:return clock_reply
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
        try:
            return f'Opening {label}.' if webbrowser.open(target, new=2) else f"I couldn't open {label} in your browser."
        except OSError:
            return f"I couldn't open {label} in your browser."
    app_match = re.fullmatch(r'(?:open|launch|start) (.{1,100})', command)
    if app_match:
        label = app_match.group(1)
        if not computer_access:
            return 'Enable computer access in Settings first, and I can open installed apps for you.'
        return open_installed_app(label)
    return None


def open_installed_app(name):
    # Resolve installed shortcuts, not arbitrary executable paths or commands.
    def normalized(value):
        return re.sub(r'[^\w]', '', value.casefold())
    requested = normalized(name)
    aliases = {'obs':'obsstudio', 'vscode':'visualstudiocode',
               'word':'microsoftword', 'excel':'microsoftexcel',
               'powerpoint':'microsoftpowerpoint', 'calc':'calculator'}
    wanted = {requested, aliases.get(requested, requested)}
    def matching(label):
        return normalized(label) in wanted
    if sys.platform == 'win32':
        system = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32'
        builtins = {'notepad':'notepad.exe','calculator':'calc.exe','paint':'mspaint.exe'}
        executable = next((builtins[key] for key in wanted if key in builtins), None)
        try:
            if executable:
                subprocess.Popen([str(system / executable)], shell=False)
                return f'Opening {name}.'
            roots = [Path(os.environ.get('APPDATA',''))/'Microsoft/Windows/Start Menu/Programs',
                     Path(os.environ.get('PROGRAMDATA',r'C:\ProgramData'))/'Microsoft/Windows/Start Menu/Programs']
            matches = {p.resolve() for root in roots if root.is_dir() for p in root.rglob('*.lnk')
                       if matching(p.stem)}
            if len(matches)==1:
                os.startfile(str(next(iter(matches))))
                return f'Opening {name}.'
            if len(matches)>1:
                return f'More than one installed shortcut matches {name}. Please use a more specific app name.'
            # Store-packaged apps may have no .lnk. Ask Windows for registered
            # Start-menu app IDs, then launch only an exact matching result.
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                                     '[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress'],
                                    capture_output=True, text=True, encoding='utf-8', errors='replace',
                                    timeout=8, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode == 0 and result.stdout.strip():
                entries = json.loads(result.stdout)
                if isinstance(entries, dict): entries = [entries]
                ids = {entry['AppID'] for entry in entries if matching(entry.get('Name',''))
                       and isinstance(entry.get('AppID'), str) and entry['AppID']}
                if len(ids) == 1:
                    os.startfile('shell:AppsFolder\\' + next(iter(ids)))
                    return f'Opening {name}.'
                if len(ids) > 1:
                    return f'More than one installed app matches {name}. Please use its exact Start menu name.'
        except (subprocess.TimeoutExpired, ValueError):
            return f'I could not check the Windows app list for {name}. Please try again.'
        except OSError:
            return f'I could not start {name}.'
    elif sys.platform == 'darwin':
        matches = [p for root in (Path('/Applications'),Path.home()/'Applications')
                   for p in root.glob('*.app') if normalized(p.stem)==normalized(name)]
        if len(matches)==1:
            try:
                subprocess.Popen(['/usr/bin/open','-a',str(matches[0])],shell=False)
                return f'Opening {name}.'
            except OSError:
                return f'I could not start {name}.'
    return f'I could not find an installed app named {name}. Try its exact Start menu name.'
