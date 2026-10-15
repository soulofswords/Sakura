"""Ephemeral, opt-in desktop audio context. No recordings are saved."""
import sys
import threading
import time
import queue
from collections import deque
import numpy as np


def sources():
    if sys.platform == 'win32':
        import pyaudiowpatch as pa
        with pa.PyAudio() as manager:
            host = manager.get_host_api_info_by_type(pa.paWASAPI)['index']
            devices = [d for d in manager.get_device_info_generator()
                       if d['hostApi'] == host and d['maxInputChannels'] > 0]
            return [{'id': 'default-output', 'kind': 'output', 'name': 'Computer audio · default speakers/headphones'}] + [
                {'id': d['name'], 'kind': 'output' if d.get('isLoopbackDevice') else 'input',
                 'name': ('Computer audio · ' if d.get('isLoopbackDevice') else 'Input · ') + d['name']}
                for d in devices]
    import sounddevice as sd
    return [{'id': d['name'], 'kind': 'input', 'name': 'Input · ' + d['name']}
            for d in sd.query_devices() if d['max_input_channels'] > 0]


def capture(source, stop, paused, seconds=4):
    """Read and drain short chunks, discarding any segment containing our speech."""
    chunks = []
    interrupted = False
    if sys.platform == 'win32':
        import pyaudiowpatch as pa
        with pa.PyAudio() as manager:
            if source == 'default-output':
                device = manager.get_default_wasapi_loopback()
            else:
                host = manager.get_host_api_info_by_type(pa.paWASAPI)['index']
                device = next(d for d in manager.get_device_info_generator()
                              if d['hostApi'] == host and d['maxInputChannels'] > 0 and d['name'] == source)
            rate = int(device['defaultSampleRate'])
            channels = min(2, int(device['maxInputChannels']))
            count = int(rate * .1)
            with manager.open(format=pa.paFloat32, channels=channels, rate=rate, input=True,
                              input_device_index=device['index'], frames_per_buffer=count) as stream:
                for _ in range(int(seconds * 10)):
                    if stop.is_set(): return np.empty(0, dtype=np.float32)
                    interrupted |= paused()
                    chunks.append(np.frombuffer(stream.read(count, exception_on_overflow=False), dtype=np.float32)
                                  .reshape(-1, channels).mean(axis=1))
    else:
        import sounddevice as sd
        device = next((i, d) for i, d in enumerate(sd.query_devices())
                      if d['name'] == source and d['max_input_channels'] > 0)
        rate = int(device[1]['default_samplerate'])
        count = int(rate * .1)
        with sd.InputStream(device=device[0], samplerate=rate, channels=1, dtype='float32') as stream:
            for _ in range(int(seconds * 10)):
                if stop.is_set(): return np.empty(0, dtype=np.float32)
                interrupted |= paused()
                chunks.append(stream.read(count)[0].flatten())
    if interrupted or not chunks: return np.empty(0, dtype=np.float32)
    samples = np.concatenate(chunks)
    # Whisper's ndarray input must always be 16 kHz, regardless of device rate.
    return np.interp(np.arange(int(len(samples) * 16000 / rate)) * rate / 16000,
                     np.arange(len(samples)), samples).astype(np.float32)


class ScreenAudio:
    def __init__(self):
        self.lock = threading.RLock()
        self.control_lock = threading.RLock()
        self.computer_only = False
        self.stop_event = threading.Event()
        self.thread = None
        self.items = deque(maxlen=8)
        self.selected = []
        self.heartbeat = 0
        self.pause_until = 0
        self.message = 'Audio listening off'

    def paused(self):
        with self.lock: return time.monotonic() < self.pause_until

    def configure(self, enabled, selected, paused, transcribe):
        with self.control_lock:
            return self._configure(enabled, selected, paused, transcribe)

    def set_computer_only(self, enabled):
        with self.control_lock:
            self.computer_only = enabled
            self.stop()

    def _configure(self, enabled, selected, paused, transcribe):
        if not enabled:
            self.stop()
            return self.status()
        if not isinstance(selected, list) or not 1 <= len(selected) <= 4 or any(not isinstance(s, str) for s in selected):
            raise ValueError('Select between one and four audio sources.')
        selected = list(dict.fromkeys(selected))
        if self.computer_only:
            outputs = {source['id'] for source in sources() if source.get('kind') == 'output'}
            if any(source not in outputs for source in selected):
                raise ValueError('AI VTuber accepts computer playback audio only, not microphones.')
        with self.lock:
            unchanged = self.thread and self.thread.is_alive() and self.selected == selected
        if not unchanged:
            allowed = {item['id'] for item in sources()}
            if any(s not in allowed for s in selected): raise ValueError('Audio source unavailable. Refresh the source list.')
            self.stop()
            with self.lock:
                self.selected = selected
                self.stop_event = threading.Event()
                self.heartbeat = time.monotonic()
                self.pause_until = self.heartbeat + 3 if paused else 0
                self.message = 'Listening to computer/input audio'
                self.thread = threading.Thread(target=self._run, args=(self.stop_event, transcribe, tuple(selected)), daemon=True)
                self.thread.start()
        with self.lock:
            self.heartbeat = time.monotonic()
            # A tail guard suppresses playback buffered just after speech ends.
            if paused: self.pause_until = self.heartbeat + 3
        return self.status()

    def _run(self, stop, transcribe, selected):
        pending = queue.Queue(maxsize=3)
        def listen(source):
            while not stop.is_set():
                with self.lock:
                    if time.monotonic() - self.heartbeat > 8: break
                try:
                    audio = capture(source, stop, self.paused)
                    if stop.is_set() or self.paused(): continue
                    if audio.size and float(np.sqrt(np.mean(audio ** 2))) > .003:
                        # Keep capturing while Whisper decodes the previous
                        # segment. Drop old backlog rather than delaying live context.
                        try: pending.put_nowait((time.monotonic(), source, audio))
                        except queue.Full:
                            try: pending.get_nowait()
                            except queue.Empty: pass
                            try: pending.put_nowait((time.monotonic(), source, audio))
                            except queue.Full: pass
                except Exception as error:
                    with self.lock:
                        if self.stop_event is stop and not stop.is_set():
                            self.message = 'Audio listening unavailable: ' + str(error)
                    break
        def recognize():
            while not stop.is_set():
                try: stamp, source, audio = pending.get(timeout=.2)
                except queue.Empty:
                    if not any(worker.is_alive() for worker in workers): break
                    continue
                if self.paused() or time.monotonic() - stamp > 8: continue
                try:
                    text = transcribe(audio).strip()
                    if text and not stop.is_set() and not self.paused() and time.monotonic() - stamp < 8:
                        with self.lock: self.items.append((stamp, source, text[:1000]))
                except Exception as error:
                    with self.lock:
                        if self.stop_event is stop and not stop.is_set():
                            self.message = 'Audio recognition unavailable: ' + str(error)
        workers = [threading.Thread(target=listen, args=(source,), daemon=True) for source in selected]
        for worker in workers: worker.start()
        recognizer = threading.Thread(target=recognize, daemon=True)
        recognizer.start()
        for worker in workers: worker.join()
        recognizer.join()
        with self.lock:
            if self.stop_event is stop and not stop.is_set() and 'unavailable' not in self.message:
                self.message = 'Audio listening stopped · screen session ended'

    def stop(self):
        with self.control_lock:
            self._stop()

    def _stop(self):
        with self.lock:
            self.stop_event.set()
            thread = self.thread
        if thread and thread is not threading.current_thread(): thread.join(timeout=5)
        with self.lock:
            self.items.clear()
            self.selected = []
            self.thread = None
            self.message = 'Audio listening off'

    def context(self):
        with self.lock:
            if not self.thread or not self.thread.is_alive() or time.monotonic() - self.heartbeat > 8: return ''
            return '\n'.join(source + ': ' + text for stamp, source, text in self.items
                             if time.monotonic() - stamp < 30)[-3000:]

    def status(self):
        with self.lock:
            return {'enabled': bool(self.thread and self.thread.is_alive()), 'message': self.message,
                    'paused': self.paused(), 'has_audio_context': bool(self.context())}


listener = ScreenAudio()
