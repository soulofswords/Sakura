"""
🔊 Text-to-Speech — multiple backends.

Backends
--------
edge-tts   : Works immediately, no setup. Cute but generic voices.
gpt-sovits : Clone any anime character's voice. Needs separate setup.
"""
import asyncio
import time
import concurrent.futures
import os
import uuid
import copy
import re
from config import (
    TTS_BACKEND, EDGE_TTS_VOICE, EDGE_TTS_VOICE_HINDI, EDGE_TTS_VOICE_HINGLISH,
    EDGE_TTS_RATE, EDGE_TTS_PITCH, GPT_SOVITS_URL, AUDIO_DIR, VOICES_DIR,
    VOICE_PRESETS, RVC_SERVER_URL, RVC_PITCH, RVC_INDEX_RATE,
)


def _run_coroutine_safely(fn, *args, **kwargs):
    """Run an async function safely whether called from a running event loop or not."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Running inside an active event loop: delegate to worker thread to avoid loop collision
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(lambda: asyncio.run(fn(*args, **kwargs)))
            return future.result()
    else:
        return asyncio.run(fn(*args, **kwargs))

def polish_spoken_text(text):
    """Keep linguistic punctuation; remove visual decoration before synthesis."""
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'^\s*(?:#{1,6}\s+|[-*•]\s+)', '', text, flags=re.MULTILINE)
    text = text.replace('**', '').replace('__', '').replace('`', '').replace('~', '')
    text = re.sub(r'[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]', '', text)
    text = re.sub(r'!{2,}', '!', text)
    text = re.sub(r'\?{2,}', '?', text)
    text = re.sub(r'\.{4,}', '...', text)
    text = re.sub(r'\s+([,.!?।])', r'\1', text)
    return re.sub(r'\s+', ' ', text).strip()


class TextToSpeech:
    def __init__(self):
        self.backend = TTS_BACKEND

        # Current active voice and speech modulation
        self.current_voice = EDGE_TTS_VOICE
        self.current_rate = EDGE_TTS_RATE
        self.current_pitch = EDGE_TTS_PITCH
        self.selected_preset_id = "sakura_ava"

        # RVC Settings (.pth and .index)
        self.rvc_model = None
        self.rvc_index = None
        self.rvc_pitch = RVC_PITCH
        self.rvc_index_rate = RVC_INDEX_RATE

        # Browser playback does not need a second native audio device.
        self._pygame = None

        if self.backend == "edge-tts":
            print(f"  🔊 TTS ready (Edge-TTS · {self.current_voice})")
        else:
            print(f"  🔊 TTS ready (GPT-SoVITS · {GPT_SOVITS_URL})")

    # ── Configuration / Voice Switching API ────────────────────
    def set_voice_preset(self, preset_id: str, custom_pitch: str = None, custom_rate: str = None):
        """Switch to one of the 10 voice presets or a custom voice."""
        if preset_id == 'nanami_japanese': preset_id = 'libby_english'
        self.selected_preset_id = preset_id

        # Check if it's one of the built-in presets
        preset = next((p for p in VOICE_PRESETS if p["id"] == preset_id), None)
        if preset and preset["voice"] != "rvc":
            self.current_voice = preset["voice"]
            self.current_rate = custom_rate or preset["rate"]
            self.current_pitch = custom_pitch or preset["pitch"]
            self.rvc_model = None
            self.rvc_index = None
            print(f"  🎭 Switched Voice: {preset['name']} ({self.current_voice})")
        elif preset_id.startswith("rvc_") or (preset and preset["voice"] == "rvc"):
            # RVC voice requested
            self.selected_preset_id = preset_id
            self.current_voice = EDGE_TTS_VOICE
            print(f"  🎭 Switched to RVC Voice Mode ({preset_id})")
        else:
            # Fallback direct voice name
            self.current_voice = preset_id
            self.rvc_model = None
            self.rvc_index = None
            if custom_rate: self.current_rate = custom_rate
            if custom_pitch: self.current_pitch = custom_pitch

    def set_rvc_model(self, model_pth: str | None, index_file: str | None = None, pitch: int = 0, index_rate: float = 0.75):
        """Configure RVC .pth and .index model files and pitch tuning."""
        self.rvc_model = model_pth
        self.rvc_index = index_file
        self.rvc_pitch = pitch
        self.rvc_index_rate = index_rate
        if model_pth:
            print(f"  🎤 RVC Model bound: {os.path.basename(model_pth)} (Index: {os.path.basename(index_file) if index_file else 'None'}, Pitch: {pitch} semitones)")

    # ── public API ─────────────────────────────────────────────
    def speak(self, text: str):
        """Generate speech from *text* and play it."""
        text = polish_spoken_text(text)
        if not text:
            return

        if self.backend == "edge-tts":
            self._speak_edge(text)
        elif self.backend == "gpt-sovits":
            self._speak_sovits(text)

    def speak_to_file(self, text: str) -> str | None:
        """Synchronous speech file generation."""
        return _run_coroutine_safely(self.speak_to_file_async, text)

    async def speak_to_file_async(self, text: str) -> str | None:
        """Asynchronous speech file generation for FastAPI."""
        text = polish_spoken_text(text)
        if not text:
            return None

        voice = copy.copy(self)
        if voice.backend == "edge-tts":
            out_file = await voice._generate_edge_async(text)
            if voice.rvc_model:
                out_file = await asyncio.to_thread(voice._apply_rvc_conversion, out_file)
            return out_file
        elif voice.backend == "gpt-sovits":
            return await asyncio.to_thread(voice._generate_sovits, text)
        return None

    # ── RVC Voice Conversion ───────────────────────────────────
    def _apply_rvc_conversion(self, audio_path: str) -> str:
        """
        Pass audio through RVC (Real-Time Voice Changer / w-okada server)
        using the selected .pth and .index files.
        """
        if not self.rvc_model:
            return audio_path

        import requests
        import mimetypes
        try:
            from rvc_manager import ensure_rvc_service
            ensure_rvc_service()
            url = f"{RVC_SERVER_URL.rstrip('/')}/voice"
            with open(audio_path, "rb") as f:
                mime_type = mimetypes.guess_type(audio_path)[0] or "application/octet-stream"
                files = {"audio": (os.path.basename(audio_path), f, mime_type)}
                data = {
                    "model": os.path.basename(self.rvc_model),
                    "f0_up_key": self.rvc_pitch,
                    "index_rate": self.rvc_index_rate,
                }
                resp = requests.post(url, files=files, data=data, timeout=120)
                if resp.status_code == 200 and len(resp.content) > 100:
                    rvc_out = str(AUDIO_DIR / f"response_rvc_{uuid.uuid4().hex}.wav")
                    with open(rvc_out, "wb") as out_f:
                        out_f.write(resp.content)
                    print(f"  ✨ [RVC] Audio transformed with character model: {os.path.basename(self.rvc_model)}")
                    return rvc_out
        except requests.RequestException:
            raise RuntimeError('The RVC voice converter is unavailable. Start your RVC conversion service '
                               'or choose a built-in voice in Settings > Voice.') from None
        raise RuntimeError('The RVC converter did not return valid audio. Check the conversion service '
                           'or choose a built-in voice in Settings > Voice.')

    # ── Edge-TTS ───────────────────────────────────────────────
    def _pick_voice(self, text: str) -> str:
        # Respect the voice the user chose, including for Hindi/Hinglish speech.
        return self.current_voice

    async def _generate_edge_async(self, text: str) -> str:
        """Generate audio file via Edge-TTS asynchronously, return path."""
        import edge_tts

        out = str(AUDIO_DIR / f"response_{uuid.uuid4().hex}.mp3")
        voice = self._pick_voice(text)

        comm = edge_tts.Communicate(
            text,
            voice,
            rate=self.current_rate,
            pitch=self.current_pitch,
        )
        await comm.save(out)
        return out

    def _generate_edge(self, text: str) -> str:
        """Synchronous wrapper for _generate_edge_async."""
        return _run_coroutine_safely(self._generate_edge_async, text)

    def _speak_edge(self, text: str):
        out = self._generate_edge(text)
        self._play(out)

    # ── GPT-SoVITS ─────────────────────────────────────────────
    def _generate_sovits(self, text: str) -> str:
        """Generate audio file via GPT-SoVITS, return path."""
        import requests

        out = str(AUDIO_DIR / f"response_{uuid.uuid4().hex}.wav")
        try:
            resp = requests.get(
                GPT_SOVITS_URL,
                params={"text": text, "text_language": "en"},
                timeout=30,
            )
            with open(out, "wb") as f:
                f.write(resp.content)
            return out

        except requests.ConnectionError:
            print("  ⚠️  GPT-SoVITS offline — falling back to Edge-TTS")
            return self._generate_edge(text)

    def _speak_sovits(self, text: str):
        out = self._generate_sovits(text)
        self._play(out)

    # ── playback ───────────────────────────────────────────────
    def _play(self, path: str):
        try:
            if self._pygame is None:
                import pygame
                pygame.mixer.init()
                self._pygame = pygame
            self._pygame.mixer.music.load(path)
            self._pygame.mixer.music.play()
            while self._pygame.mixer.music.get_busy():
                time.sleep(0.05)
        except Exception as exc:
            print(f"  ⚠️  Playback error: {exc}")

    def cleanup(self):
        if self._pygame is not None:
            self._pygame.mixer.quit()
