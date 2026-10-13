"""
🎤 Speech-to-Text — Faster-Whisper with live mic recording.
Records until silence is detected, then transcribes.
"""
import numpy as np
import sounddevice as sd
import soundfile as sf
from config import (
    WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE,
    SAMPLE_RATE, SILENCE_THRESHOLD, SILENCE_DURATION,
    MAX_RECORD_SECONDS, AUDIO_DIR,
)


class SpeechToText:
    def __init__(self):
        from faster_whisper import WhisperModel

        print(f"  🎤 Loading Whisper ({WHISPER_MODEL}) on {WHISPER_DEVICE}...")
        self.model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE,
        )
        print("  🎤 Whisper ready!")
        # Speech recognition remains usable even if the optional silence
        # detector cannot load (for example after a broken package install).
        try:
            from faster_whisper.vad import get_vad_model
            get_vad_model()
            self.vad_available = True
        except (ImportError, RuntimeError, OSError):
            self.vad_available = False
            print("  🎤 Silence filter unavailable; transcribing without VAD.")

    # ── recording ──────────────────────────────────────────────
    def record_audio(self) -> np.ndarray:
        """Record from the default mic until the user stops speaking."""
        print("\n🎤 Listening… (speak now)")

        chunk_dur = 0.1  # 100 ms per read
        chunk_samples = int(SAMPLE_RATE * chunk_dur)
        max_chunks = int(MAX_RECORD_SECONDS / chunk_dur)

        chunks: list[np.ndarray] = []
        silent_count = 0
        silent_needed = int(SILENCE_DURATION / chunk_dur)
        heard_speech = False

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as stream:
            for _ in range(max_chunks):
                data, _ = stream.read(chunk_samples)
                chunks.append(data.copy())

                rms = float(np.sqrt(np.mean(data ** 2)))

                if rms > SILENCE_THRESHOLD:
                    heard_speech = True
                    silent_count = 0
                else:
                    silent_count += 1

                # Stop once speech ended
                if heard_speech and silent_count >= silent_needed:
                    break

        if not heard_speech:
            return np.array([], dtype=np.float32)

        return np.concatenate(chunks).flatten()

    # ── transcription ──────────────────────────────────────────
    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""

        # Browser recordings can be very quiet even when the microphone is
        # working. Normalize only quiet input so Whisper receives a usable
        # signal without clipping normally recorded speech.
        audio = np.asarray(audio, dtype=np.float32).flatten()
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak < 0.008:
            return ""
        if peak < 0.20:
            audio = np.clip(audio * (0.20 / peak), -1.0, 1.0)

        # Code-switching prompt enables Whisper to seamlessly handle mid-sentence transitions between Hindi and English
        code_switch_prompt = "Hello Sakura! नमस्ते साकुरा, arre yaar, let's write code together. Please help me with this problem."
        segments, info = self.model.transcribe(
            audio,
            language=None,
            initial_prompt=code_switch_prompt,
            vad_filter=getattr(self, 'vad_available', False),
            vad_parameters=dict(min_silence_duration_ms=400),
            beam_size=5,
            condition_on_previous_text=False,
        )
        text = " ".join(seg.text for seg in segments).strip()
        if text:
            return text

        # Short phrases can be discarded by VAD. Retry once without VAD so a
        # quick greeting such as “hello, how are you?” is still recognized.
        segments, _ = self.model.transcribe(
            audio,
            language="en",
            beam_size=3,
            condition_on_previous_text=False,
            vad_filter=False,
        )
        return " ".join(seg.text for seg in segments).strip()

    # ── convenience ────────────────────────────────────────────
    def listen(self) -> str:
        """Record → transcribe in one call."""
        audio = self.record_audio()
        if audio.size == 0:
            return ""
        return self.transcribe(audio)
