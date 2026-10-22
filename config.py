"""
🌸 Sakura — Configuration
All settings in one place. Tweak these to customize your assistant.
"""
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ──────────────────────── Paths ────────────────────────
BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio"
MODELS_DIR = BASE_DIR / "models"
VOICES_DIR = BASE_DIR / "voices"
PERSONALITY_DIR = BASE_DIR / "personality"
AUDIO_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)
VOICES_DIR.mkdir(exist_ok=True)

# ──────────────────────── LLM (Ollama) ────────────────────────
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen3-vl:4b-instruct"
OLLAMA_VISION_MODEL = "qwen3-vl:4b-instruct"
# Other good options:  "mistral:7b", "qwen2.5:7b", "phi3:mini", "gemma2:9b"

# ──────────────────────── STT (Faster-Whisper) ────────────────────────
WHISPER_MODEL = "base"          # tiny (fast CPU) | base | small | medium | large-v3
WHISPER_DEVICE = "cpu"          # "cuda" for GPU (requires PyTorch+CUDA), "cpu" for CPU-only
WHISPER_COMPUTE = "int8"        # "float16" for GPU, "int8" for CPU
SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.02        # RMS energy below this = silence
SILENCE_DURATION = 0.7          # seconds of silence → stop recording
MAX_RECORD_SECONDS = 30         # hard cap on recording length

# ──────────────────────── TTS & Character Voices ────────────────────────
TTS_BACKEND = "kokoro"
from voice_catalog import VOICE_PRESETS, voice_language, canonical_voice_id, DEFAULT_VOICE_ID
KOKORO_VOICE = "af_heart"
TTS_RATE = "+0%"
TTS_PITCH = "+0Hz"

# ──────────────────────── GPT-SoVITS (optional) ────────────────────────
GPT_SOVITS_URL = "http://127.0.0.1:9880"

# ──────────────────────── RVC Voice Changer ────────────────────────
# Connects to local Real-Time Voice Changer (w-okada) or local RVC
RVC_SERVER_URL = "http://127.0.0.1:18888"
RVC_PITCH = 0                    # semitones (-12 to +12, +12 for male-to-female)
RVC_INDEX_RATE = 0.75            # feature index retrieval strength (0.0 - 1.0)

# ──────────────────────── Wake Word ────────────────────────
WAKE_WORD_ENABLED = False       # Set True to require "Hey Sakura" before each query
WAKE_WORD = "hey sakura"
WAKE_WORD_THRESHOLD = 0.5       # detection confidence threshold

# ──────────────────────── Personality ────────────────────────
ASSISTANT_NAME = "Sakura"
