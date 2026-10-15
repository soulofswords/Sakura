"""Offline Windows speech rendered to a file; never takes over an audio device."""
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import wave
from functools import lru_cache
import hashlib
import shutil


def _speech_host():
    # Modern System.Speech exposes additional OneCore voices on newer PCs.
    # Enumeration and synthesis must use the same host; Windows PowerShell
    # remains the dependency-free fallback on a clean installation.
    return shutil.which('pwsh') or str(Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe')

_LIST_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    @($synth.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object {
        @{ name = $_.VoiceInfo.Name; gender = $_.VoiceInfo.Gender.ToString(); culture = $_.VoiceInfo.Culture.Name }
    }) | ConvertTo-Json -Compress
} finally { $synth.Dispose() }
'''

_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$spec = [Console]::In.ReadToEnd() | ConvertFrom-Json
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $voices = @($synth.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.TwoLetterISOLanguageName -eq $spec.language })
    if ($voices.Count -eq 0) { throw 'No installed voice for the selected language.' }
    $preferred = @($voices | Where-Object { $_.VoiceInfo.Gender.ToString() -eq $spec.gender })
    if ($preferred.Count -eq 0) { throw 'No installed voice for the selected gender and language.' }
    if ($spec.voice) {
        $preferred = @($preferred | Where-Object { $_.VoiceInfo.Name -eq $spec.voice })
        if ($preferred.Count -eq 0) { throw 'The selected Windows voice is no longer installed.' }
    }
    $synth.SelectVoice($preferred[0].VoiceInfo.Name)
    $synth.Rate = [int]$spec.rate
    $synth.SetOutputToWaveFile($spec.path)
    $synth.Speak($spec.text)
    $synth.SetOutputToNull()
} finally { $synth.Dispose() }
'''


@lru_cache(maxsize=1)
def system_voice_presets():
    if sys.platform != 'win32':return []
    command = _speech_host()
    try:
        result = subprocess.run([str(command), '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand',
            base64.b64encode(_LIST_SCRIPT.encode('utf-16le')).decode('ascii')], capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        if result.returncode:return []
        rows = json.loads(result.stdout.decode('utf-8-sig'))
        if isinstance(rows, dict):rows = [rows]
        presets=[];seen=set()
        for row in rows or []:
            language = row['culture'].split('-')[0]
            if language not in {'en', 'hi'} or row['gender'] not in {'Male','Female'}:continue
            name = row['name']
            alias=name.lower().removesuffix(' desktop')
            if alias in seen:continue
            seen.add(alias)
            presets.append({'id': 'system_'+language+'_'+hashlib.sha256(name.encode('utf-8')).hexdigest()[:16],
                'name':name, 'system_name':name, 'voice':'system', 'backend':'system', 'gender':row['gender'],
                'language':'Hindi' if language=='hi' else 'English', 'rate':'+0%', 'pitch':'+0Hz',
                'desc':f"Offline · {row['gender']} · {row['culture']} · installed Windows voice"})
        return presets
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):return []


def render_system_speech(text, path, *, language='English', gender='Female', rate='+0%', voice=None):
    if sys.platform != 'win32':
        raise RuntimeError('The online speech service is unavailable. Offline fallback currently requires Windows.')
    # Keep Hindi/Hinglish on a Hindi-capable voice; never switch them to English.
    locale = 'hi' if language in {'Hindi', 'Hinglish'} else 'en'
    percent = re.fullmatch(r'([+-]?\d+)%', rate)
    speed = max(-10, min(10, round(int(percent[1]) / 10))) if percent else 0
    payload = {'text': text, 'path': str(Path(path).resolve()), 'language': locale, 'gender': gender, 'rate': speed, 'voice':voice}
    command = _speech_host()
    encoded = base64.b64encode(_SCRIPT.encode('utf-16le')).decode('ascii')
    try:
        result = subprocess.run([str(command), '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
            input=json.dumps(payload, ensure_ascii=False).encode('utf-8'), capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=max(30, min(180, len(text) / 10)))
        if result.returncode:
            raise RuntimeError(f'Offline speech needs an installed Windows {language} {gender.lower()} voice. Add its speech pack in Windows Settings, or retry the online voice later.')
        with wave.open(str(path), 'rb') as audio:
            if not audio.getnframes() or not audio.getframerate():
                raise RuntimeError('Offline speech returned an empty audio file.')
        return str(path)
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise
