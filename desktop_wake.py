"""Optional offline Windows wake listener, independent of Chromium visibility/timers."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
import urllib.request
import zipfile

MODEL_HASH='30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498'
DLL_HASH='6994ddc68556c7e5730c3b6f6bad13320e3519b13ce3ed2aa25a86724e7c10ac'
MODEL_URL='https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip'
DLL_URL='https://files.pythonhosted.org/packages/c0/4c/deb0861f7da9696f8a255f1731bb73e9412cca29c4b3888a3fcb2a930a59/vosk-0.3.45-py3-none-win_amd64.whl'

def phrase_words(text):
    phrase=re.sub(r' +',' ',re.sub('[^a-z ]',' ',str(text).lower()).strip())
    if not re.fullmatch("[A-Za-z '-]{3,70}",str(text)) or not 2<=len(phrase.split())<=6:
        raise ValueError('Use a wake phrase of 2–6 English words, such as Hey Sakura.')
    return phrase

class DesktopWake:
    def __init__(self,root,on_command,on_status=lambda message:None):
        self.root=Path(root)/'desktop-profile'/'wake'
        self.on_command=on_command;self.on_status=on_status
        self.thread=None;self.cancel=threading.Event();self.recording=threading.Event()
        self.busy=False;self.status='Wake listener off';self.phrase='hey sakura'
        self._install_lock=threading.Lock();self._dll_directory=None

    @property
    def model(self):return self.root/'vosk-model-small-en-us-0.15'
    def state(self):
        return dict(available=sys.platform=='win32',installed=(self.model/'ready.sha256').is_file() and (self.root/'native/libvosk.dll').is_file(),
                    enabled=bool(self.thread and self.thread.is_alive() and not self.cancel.is_set()),status=self.status,phrase=self.phrase)
    def _status(self,text):
        self.status=text
        self.on_status(text)
    def install(self):
        if sys.platform!='win32':raise RuntimeError('The native wake pack currently supports Windows x64. Use desktop listening on this platform.')
        with self._install_lock:
            if self.state()['installed']:return self.state()
            self.root.mkdir(parents=True,exist_ok=True)
            for name,url,digest in [('model.zip',MODEL_URL,MODEL_HASH),('runtime.whl',DLL_URL,DLL_HASH)]:
                download=self.root/(name+'.download');self._status('Downloading optional offline wake pack…')
                try:
                    h=hashlib.sha256();size=0
                    with urllib.request.urlopen(url,timeout=25) as response,download.open('wb') as out:
                        while block:=response.read(65536):
                            size+=len(block)
                            if size>50000000:raise RuntimeError('Wake download exceeds size limit.')
                            h.update(block);out.write(block)
                    if h.hexdigest()!=digest:raise RuntimeError('Wake download integrity check failed.')
                    with zipfile.ZipFile(download) as z:
                        total=0
                        if name=='model.zip':
                            for item in z.infolist():
                                target=(self.root/item.filename).resolve()
                                if not target.is_relative_to(self.root.resolve()):raise RuntimeError('Unsafe wake pack path.')
                                total+=item.file_size
                                if total>120000000 or len(z.infolist())>100:raise RuntimeError('Wake pack is too large.')
                                if item.is_dir():target.mkdir(parents=True,exist_ok=True)
                                else:
                                    target.parent.mkdir(parents=True,exist_ok=True)
                                    with z.open(item) as source,target.open('wb') as out:
                                        import shutil
                                        shutil.copyfileobj(source,out)
                        else:
                            native=self.root/'native';native.mkdir(exist_ok=True)
                            for item in z.infolist():
                                if item.filename.endswith('.dll'):(native/Path(item.filename).name).write_bytes(z.read(item))
                finally:download.unlink(missing_ok=True)
            (self.model/'ready.sha256').write_text(MODEL_HASH,encoding='ascii')
            self._status('Wake pack ready · enable the wake phrase to listen')
            return self.state()
    def start(self,phrase):
        phrase=phrase_words(phrase)
        if not self.state()['installed']:raise RuntimeError('Download the optional wake pack first.')
        if self.state()['enabled'] and phrase==self.phrase:return self.state()
        self.stop()
        if self.thread and self.thread.is_alive():raise RuntimeError("Previous wake listener is still stopping. Retry shortly.")
        self.phrase=phrase;self.busy=False;self.cancel=threading.Event()
        self.thread=threading.Thread(target=self._run,name='SakuraWake',daemon=True);self.thread.start()
        return self.state()
    def stop(self):
        self.cancel.set()
        if self.thread and self.thread is not threading.current_thread():self.thread.join(timeout=2)
        self._status('Wake listener off')
    def pause(self,value):
        self.busy=bool(value)
        if value:
            deadline=time.monotonic()+1
            while self.recording.is_set() and time.monotonic()<deadline:time.sleep(.02)
    def _library(self,native=None):
        native=Path(native) if native else self.root/'native'
        if self._dll_directory is None:self._dll_directory=os.add_dll_directory(str(native))
        lib=ctypes.CDLL(str(native/'libvosk.dll'));p=ctypes.c_void_p
        signatures={
            'vosk_model_new':([ctypes.c_char_p],p),'vosk_model_free':([p],None),
            'vosk_model_find_word':([p,ctypes.c_char_p],ctypes.c_int),
            'vosk_recognizer_new_grm':([p,ctypes.c_float,ctypes.c_char_p],p),
            'vosk_recognizer_new':([p,ctypes.c_float],p),
            'vosk_recognizer_accept_waveform':([p,ctypes.c_void_p,ctypes.c_int],ctypes.c_int),
            'vosk_recognizer_result':([p],ctypes.c_char_p),'vosk_recognizer_partial_result':([p],ctypes.c_char_p),
            'vosk_recognizer_final_result':([p],ctypes.c_char_p),
            'vosk_recognizer_set_words':([p,ctypes.c_int],None),'vosk_recognizer_free':([p],None),'vosk_recognizer_reset':([p],None)}
        for name,(args,restype) in signatures.items():getattr(lib,name).argtypes=args;getattr(lib,name).restype=restype
        lib.vosk_set_log_level(-1);return lib
    def _run(self):
        model=wake=None;lib=None
        try:
            import sounddevice as sd
            lib=self._library();model=lib.vosk_model_new(str(self.model).encode('utf-8'))
            if not model:raise RuntimeError('Offline wake model could not load.')
            for word in self.phrase.split():
                if lib.vosk_model_find_word(model,word.encode())<0:raise ValueError(f'The wake pack does not know “{word}”. Choose different English words.')
            wake=lib.vosk_recognizer_new_grm(model,16000,json.dumps([self.phrase,'[unk]']).encode())
            if not wake:raise RuntimeError('Wake recognizer could not start.')
            while not self.cancel.is_set():
                if self.busy:self.cancel.wait(.2);continue
                self._status(f'Listening offline for “{self.phrase}”')
                lib.vosk_recognizer_reset(wake);detected=False;utterance=bytearray()
                with sd.RawInputStream(samplerate=16000,blocksize=3200,channels=1,dtype='int16') as stream:
                    self.recording.set()
                    try:
                        while not self.cancel.is_set() and not self.busy:
                            data,_=stream.read(3200);b=bytes(data);complete=lib.vosk_recognizer_accept_waveform(wake,b,len(b))
                            text=json.loads((lib.vosk_recognizer_result(wake) if complete else lib.vosk_recognizer_partial_result(wake)).decode()).get('text' if complete else 'partial','')
                            utterance.extend(b)
                            if len(utterance)>256000:del utterance[:-256000]
                            if complete:
                                if text==self.phrase:
                                    verifier=lib.vosk_recognizer_new(model,16000)
                                    try:
                                        lib.vosk_recognizer_set_words(verifier,1);audio=bytes(utterance)
                                        evidence_list=[]
                                        for offset in range(0,len(audio),6400):
                                            piece=audio[offset:offset+6400]
                                            if lib.vosk_recognizer_accept_waveform(verifier,piece,len(piece)):evidence_list.append(json.loads(lib.vosk_recognizer_result(verifier).decode()))
                                        evidence_list.append(json.loads(lib.vosk_recognizer_final_result(verifier).decode()))
                                        for evidence in evidence_list:
                                            words=evidence.get('result',[]);confidence=[w.get('conf',0) for w in words]
                                            duration=words[-1].get('end',0)-words[0].get('start',0) if words else 0
                                            if evidence.get('text')==self.phrase and len(words)==len(self.phrase.split()) and .35<=duration<=4.5 and min(confidence,default=0)>=.85 and sum(confidence)/max(1,len(confidence))>=.92:detected=True;break
                                    finally:lib.vosk_recognizer_free(verifier)
                                if len(utterance)>64000:del utterance[:-64000]
                                if detected:break
                    finally:self.recording.clear()
                if not detected or self.cancel.is_set() or self.busy:continue
                self._status('Wake phrase heard · ask after the tone')
                try:
                    import winsound
                    winsound.Beep(900,100)
                except RuntimeError:pass
                speech=lib.vosk_recognizer_new(model,16000);text='';command_audio=bytearray()
                try:
                    deadline=time.monotonic()+14
                    with sd.RawInputStream(samplerate=16000,blocksize=3200,channels=1,dtype='int16') as stream:
                        self.recording.set()
                        try:
                            while not self.cancel.is_set() and not self.busy and time.monotonic()<deadline:
                                data,_=stream.read(3200);b=bytes(data);command_audio.extend(b)
                                if lib.vosk_recognizer_accept_waveform(speech,b,len(b)):
                                    text=json.loads(lib.vosk_recognizer_result(speech).decode()).get('text','')
                                    if text and text!=self.phrase:break
                            if not text:text=json.loads(lib.vosk_recognizer_final_result(speech).decode()).get('text','')
                        finally:self.recording.clear()
                finally:lib.vosk_recognizer_free(speech)
                if text.startswith(self.phrase+' '):text=text[len(self.phrase)+1:]
                if re.fullmatch(r'(?:(?:huh|uh|um|hm|hmm|ah|oh|eh|er|erm|ha|mm) ?)+',text):text=''
                if text and text!=self.phrase and not self.cancel.is_set() and not self.busy:
                    import io,wave
                    from speaker_profiles import accepts_microphone
                    clip=io.BytesIO()
                    with wave.open(clip,'wb') as wav:
                        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(command_audio)
                    if not accepts_microphone(clip.getvalue()):
                        self._status('Voice not recognised · waiting for the wake phrase');continue
                    self.busy=True;self._status('Answering · wake microphone paused')
                    try:self.on_command(text)
                    except Exception:self.busy=False;raise
        except Exception as error:self._status(f'Wake listener stopped: {error}')
        finally:
            self.recording.clear()
            if lib and wake:lib.vosk_recognizer_free(wake)
            if lib and model:lib.vosk_model_free(model)
