"""Shared CPU Kokoro runtime. Speech stays local after the asset download."""
import hashlib
import os
from pathlib import Path
import re
import threading
import uuid
from config import BASE_DIR

ASSETS_DIR=BASE_DIR/'kokoro-assets'
ASSETS={
    'kokoro-v1.0.int8.onnx':(92361271,'6e742170d309016e5891a994e1ce1559c702a2ccd0075e67ef7157974f6406cb'),
    'voices-v1.0.bin':(28214398,'bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d'),
}
ASSET_URL='https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'
_prepare_lock=threading.Lock()
_synthesis_lock=threading.Lock()
_engine=None
_status={'phase':'idle','progress':0,'message':'Local Kokoro loads when speech is first used.'}


def status():return dict(_status)


def _set(phase,message,progress=0):_status.update(phase=phase,message=message,progress=progress)


def _hash(path):
    digest=hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda:file.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def ensure_assets():
    import requests
    ASSETS_DIR.mkdir(parents=True,exist_ok=True)
    total=sum(size for size,_ in ASSETS.values());complete=0
    for name,(size,digest) in ASSETS.items():
        target=ASSETS_DIR/name
        _set('verifying','Verifying local Kokoro speech files…',round(complete/total*100))
        if target.is_file() and target.stat().st_size==size and _hash(target)==digest:
            complete+=size;continue
        temporary=target.with_suffix(target.suffix+'.'+uuid.uuid4().hex+'.part')
        try:
            _set('downloading','Downloading local Kokoro speech files (about 121 MB)…',round(complete/total*100))
            with requests.get(ASSET_URL+name,stream=True,timeout=(15,60)) as response:
                response.raise_for_status();count=0
                with temporary.open('wb') as file:
                    for chunk in response.iter_content(1024*1024):
                        count+=len(chunk)
                        if count>size:raise RuntimeError('The Kokoro download exceeded its expected size.')
                        file.write(chunk);_set('downloading','Downloading local Kokoro speech files…',round((complete+count)/total*100))
            if temporary.stat().st_size!=size or _hash(temporary)!=digest:
                raise RuntimeError('Kokoro download verification failed. Retry the download.')
            temporary.replace(target);complete+=size
        finally:temporary.unlink(missing_ok=True)


def prepare():
    global _engine
    with _prepare_lock:
        if _engine is not None:return status()
        try:
            ensure_assets()
            _set('loading','Loading local Kokoro voices…',100)
            import onnxruntime as ort
            from kokoro_onnx import Kokoro
            options=ort.SessionOptions()
            options.intra_op_num_threads=max(1,min(4,(os.cpu_count() or 4)//4))
            options.inter_op_num_threads=1
            session=ort.InferenceSession(str(ASSETS_DIR/'kokoro-v1.0.int8.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
            _engine=Kokoro.from_session(session,str(ASSETS_DIR/'voices-v1.0.bin'))
            # Initialize the phonemizer and lazy inference kernels while the
            # AI is still preparing its answer, rather than on its first word.
            _engine.create('Ready.',voice='af_heart',lang='en-us')
            _set('ready','Local Kokoro is ready. Speech works offline.',100)
        except Exception as exc:
            _engine=None
            _set('error','Local Kokoro could not start: '+str(exc))
            raise RuntimeError(_status['message']) from None
        return status()


def render_speech(text,path,*,voice='af_heart',language='English',locale='en-us',rate='+0%'):
    prepare()
    import numpy as np
    import soundfile as sf
    match=re.fullmatch(r'([+-]?\d+)%',rate)
    speed=max(.5,min(2,1+int(match[1])/100)) if match else 1.0
    if language=='English' and locale not in {'en-us','en-gb'}:raise ValueError('Choose an English Kokoro voice.')
    if language in {'Hindi','Hinglish'}:locale='hi'
    try:
        # Bound CPU contention when the chat pipeline prefetches phrases while
        # face tracking and the renderer are active.
        with _synthesis_lock:
            samples,sample_rate=_engine.create(text,voice=voice,speed=speed,lang=locale)
        samples=np.asarray(samples,dtype=np.float32)
        if not samples.size or not np.isfinite(samples).all() or not np.any(np.abs(samples)>1e-5):
            raise RuntimeError('Kokoro returned empty or invalid speech.')
        sf.write(str(path),samples,sample_rate,subtype='PCM_16')
        return str(path)
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise
