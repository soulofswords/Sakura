"""Launch verified Steam library shortcuts through Steam, without shell commands."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SHORTCUTS = Path(__file__).with_name('steam-shortcuts.json')


def steam_executable():
    if sys.platform == 'darwin':
        return next((p for p in (Path('/Applications/Steam.app'), Path.home() / 'Applications/Steam.app') if p.is_dir()), None)
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
            executable = Path(winreg.QueryValueEx(key, 'SteamExe')[0])
            if executable.is_file():
                return executable
    except (ImportError, OSError):
        pass
    for root in (os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)'), os.environ.get('PROGRAMFILES', r'C:\Program Files')):
        executable = Path(root) / 'Steam/steam.exe'
        if executable.is_file():
            return executable
    return None


def epic_executable():
    if sys.platform == 'darwin':
        return next((p for p in (Path('/Applications/Epic Games Launcher.app'), Path.home() / 'Applications/Epic Games Launcher.app') if p.is_dir()), None)
    roots = [Path(os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)')),
             Path(os.environ.get('PROGRAMFILES', r'C:\Program Files'))]
    for root in roots:
        for arch in ('Win64', 'Win32'):
            executable = root / 'Epic Games/Launcher/Portal/Binaries' / arch / 'EpicGamesLauncher.exe'
            if executable.is_file():
                return executable
    return None


def installed_games():
    """Read installed library manifests; never download or install games."""
    games = []
    executable = steam_executable()
    if executable:
        steam_root = Path.home() / 'Library/Application Support/Steam' if sys.platform == 'darwin' else executable.parent
        roots = {steam_root}
        libraries = steam_root / 'steamapps/libraryfolders.vdf'
        try:
            roots.update(Path(value.replace('\\\\', '\\')) for value in re.findall(r'"path"\s+"([^"\n]+)"', libraries.read_text(encoding='utf-8')))
        except OSError:
            pass
        for root in roots:
            for manifest in (root / 'steamapps').glob('appmanifest_*.acf'):
                try:
                    fields = dict(re.findall(r'"([^"\n]+)"\s+"([^"\n]*)"', manifest.read_text(encoding='utf-8')))
                    if fields.get('appid', '').isdigit() and fields.get('name'):
                        games.append({'name': fields['name'], 'url': 'steam://rungameid/' + fields['appid'], 'store': 'steam', 'install_dir': str(root / 'steamapps/common' / fields.get('installdir', ''))})
                except (OSError, UnicodeError):
                    continue
    epic = (Path.home() / 'Library/Application Support/Epic/EpicGamesLauncher/Data/Manifests' if sys.platform == 'darwin'
            else Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData')) / 'Epic/EpicGamesLauncher/Data/Manifests')
    for manifest in epic.glob('*.item'):
        try:
            data = json.loads(manifest.read_text(encoding='utf-8-sig'))
            identifier = data.get('AppName', '')
            namespace = data.get('CatalogNamespace', '')
            item = data.get('CatalogItemId', '')
            if all(re.fullmatch(r'[A-Za-z0-9_-]+', part or '') for part in (namespace, item, identifier)):
                identifier = '%3A'.join((namespace, item, identifier))
            if data.get('DisplayName') and re.fullmatch(r'[A-Za-z0-9_%:-]+', identifier) and Path(data.get('InstallLocation', '')).is_dir():
                games.append({'name': data['DisplayName'], 'url': 'com.epicgames.launcher://apps/' + identifier + '?action=launch&silent=true', 'store': 'epic', 'install_dir': data['InstallLocation']})
        except (OSError, ValueError):
            continue
    return games


def normalize_game_name(value):
    value = value.lower()
    for word, digit in {'one':'1', 'two':'2', 'three':'3', 'four':'4', 'five':'5', 'six':'6', 'seven':'7', 'eight':'8', 'nine':'9', 'ten':'10'}.items():
        value = re.sub(r'\b' + word + r'\b', digit, value)
    value = re.sub(r'\bleft for dead\b', 'left 4 dead', value)
    compact = re.sub(r'[^a-z0-9]', '', value)
    return {'l4d2':'left4dead2', 'l4d':'left4dead'}.get(compact, compact)


def run_steam_command(command, computer_access):
    command = re.sub(r'\bepic games? launcher\b', 'epic games', command)
    epic_only = bool(re.fullmatch(r'(?:open|launch|start) epic(?: games)?(?: library)?', command))
    steam_only = command in {'open steam', 'launch steam', 'start steam', 'open steam library'}
    query = re.sub(r'^open (?:steam|epic(?: games)?) and ', '', command)
    store = 'epic' if re.search(r'epic(?: games)?(?: library(?: list)?)?$', query) else 'steam' if 'steam' in query else None
    explicit = bool(re.search(r' (?:from|in|on) (?:the )?(?:steam|epic(?: games)?)(?: library(?: list)?)?$', query))
    query = re.sub(r' (?:from|in|on) (?:the )?(?:steam|epic(?: games)?)(?: library(?: list)?)?$', '', query)
    match = re.fullmatch(r'(?:open|run|launch|play|start) (.+)', query)
    selected = None
    if match:
        normalize = normalize_game_name
        requested = normalize(match.group(1))
        try:
            games = json.loads(SHORTCUTS.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            games = []
        games += installed_games()
        for game in games:
            if store and game.get('store', 'steam') != store:
                continue
            if requested in {normalize(game['name']), normalize(game.get('library_name', game['name']))}:
                selected = game
                break
    if not steam_only and not epic_only and selected is None and not explicit:
        return None
    if not computer_access:
        return 'Enable computer access in Settings first, and I can open Steam or your game.'
    if not steam_only and not epic_only and selected is None:
        return "I don't have a verified Steam library shortcut for that game yet."
    if epic_only or (selected and selected.get('store') == 'epic'):
        try:
            url = 'com.epicgames.launcher://library' if epic_only else selected['url']
            executable = epic_executable()
            if executable is None:
                return "I couldn't find Epic Games Launcher installed on this computer."
            args = ['/usr/bin/open', '-a', str(executable)] if sys.platform == 'darwin' else [str(executable)]
            subprocess.Popen(args if epic_only else args + [url], shell=False)
            return 'Opening Epic Games Launcher.' if epic_only else f"Launching {selected['name']} from Epic Games."
        except OSError:
            return "I couldn't open Epic Games Launcher. Check that it is installed."
    executable = steam_executable()
    if executable is None:
        return "I couldn't find Steam installed on this computer."
    url = 'steam://open/library' if steam_only else selected['url']
    if not steam_only and not epic_only and not re.fullmatch(r'steam://rungameid/[0-9]+', url):
        return 'That Steam game shortcut is invalid.'
    try:
        args = ['/usr/bin/open', '-a', str(executable), url] if sys.platform == 'darwin' else [str(executable), url]
        subprocess.Popen(args, shell=False)
    except OSError:
        return "I couldn't start Steam. Try opening Steam manually once."
    return 'Opening your Steam library.' if steam_only else f"Launching {selected['name']} from Steam."
