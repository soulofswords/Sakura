import os
import shutil
import subprocess


MAX_BYTES=4*1024*1024
MAX_SECONDS=120


def transcribe(content,recognizer):
    if not isinstance(content,bytes) or not content or len(content)>MAX_BYTES:raise ValueError('Choose a voice memo under 4 MB and two minutes.')
    if content.startswith(b'OggS'):format_name='ogg'
    elif content.startswith(b'RIFF') and content[8:12]==b'WAVE':format_name='wav'
    elif content.startswith(b'\x1a\x45\xdf\xa3'):format_name='matroska'
    else:raise ValueError('Supported voice memos are OGG/Opus, WAV and WebM.')
    if recognizer is None:raise ValueError('Load Sakura speech recognition on this PC before transcribing a memo.')
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:
        from audio_decode import decode_audio
        text=recognizer(decode_audio(content,MAX_SECONDS))
        if not isinstance(text,str):raise ValueError('Speech recognition returned no transcript.')
        return text[:8000]
    try:
        decoded=subprocess.run([ffmpeg,'-nostdin','-hide_banner','-loglevel','error','-protocol_whitelist','pipe','-f',format_name,
                                '-i','pipe:0','-t',str(MAX_SECONDS+1),'-ar','16000','-ac','1','-f','f32le','pipe:1'],
                               input=content,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=15,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    except subprocess.TimeoutExpired:raise ValueError('Voice memo decoding timed out.') from None
    if decoded.returncode or not decoded.stdout:raise ValueError('Could not decode this voice memo.')
    if len(decoded.stdout)>MAX_SECONDS*16000*4:raise ValueError('Voice memos must be at most two minutes.')
    import numpy as np
    audio=np.frombuffer(decoded.stdout,dtype='<f4').copy()
    if not np.isfinite(audio).all():raise ValueError('Voice memo contains invalid audio samples.')
    text=recognizer(audio)
    if not isinstance(text,str):raise ValueError('Speech recognition returned no transcript.')
    return text[:8000]
