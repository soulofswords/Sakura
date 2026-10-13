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
WHISPER_MODEL = "tiny"          # tiny (fast CPU) | base | small | medium | large-v3
WHISPER_DEVICE = "cpu"          # "cuda" for GPU (requires PyTorch+CUDA), "cpu" for CPU-only
WHISPER_COMPUTE = "int8"        # "float16" for GPU, "int8" for CPU
SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.02        # RMS energy below this = silence
SILENCE_DURATION = 1.5          # seconds of silence → stop recording
MAX_RECORD_SECONDS = 30         # hard cap on recording length

# ──────────────────────── TTS & Character Voices ────────────────────────
TTS_BACKEND = "edge-tts"
# Default natural anime heroine voice (sweet, natural, mature — NOT baby voice)
EDGE_TTS_VOICE = "en-US-AvaNeural"
EDGE_TTS_VOICE_HINDI = "hi-IN-SwaraNeural"
EDGE_TTS_VOICE_HINGLISH = "en-IN-NeerjaExpressiveNeural"
EDGE_TTS_RATE = "+0%"            # normal speed
EDGE_TTS_PITCH = "+0Hz"          # natural pitch (0Hz avoids high cartoon baby voice)

# English voice groups, plus dedicated Hindi and Hinglish voices.
VOICE_PRESETS = []
for gender, entries in (
    ("Female", [
        ("sakura_ava", "Sakura · Ava", "en-US-AvaNeural"),
        ("emma_energetic", "Emma", "en-US-EmmaNeural"),
        ("jenny_companion", "Jenny", "en-US-JennyNeural"),
        ("michelle_soft", "Michelle", "en-US-MichelleNeural"),
        ("sonia_maid", "Sonia", "en-GB-SoniaNeural"),
        ("aria_confident", "Aria", "en-US-AriaNeural"),
        ("libby_english", "Libby", "en-GB-LibbyNeural"),
        ("natasha_english", "Natasha", "en-AU-NatashaNeural"),
        ("clara_english", "Clara", "en-CA-ClaraNeural"),
        ("ana_english", "Ana", "en-US-AnaNeural"),
    ]),
    ("Male", [
        ("guy_english", "Guy", "en-US-GuyNeural"),
        ("andrew_english", "Andrew", "en-US-AndrewNeural"),
        ("brian_english", "Brian", "en-US-BrianNeural"),
        ("christopher_english", "Christopher", "en-US-ChristopherNeural"),
        ("eric_english", "Eric", "en-US-EricNeural"),
        ("roger_english", "Roger", "en-US-RogerNeural"),
        ("steffan_english", "Steffan", "en-US-SteffanNeural"),
        ("ryan_english", "Ryan", "en-GB-RyanNeural"),
        ("thomas_english", "Thomas", "en-GB-ThomasNeural"),
        ("liam_english", "Liam", "en-CA-LiamNeural"),
    ]),
):
    for preset_id, name, voice in entries:
        VOICE_PRESETS.append({"id":preset_id,"name":name,"voice":voice,"gender":gender,
            "language":"English","rate":"+5%" if preset_id=="emma_energetic" else "-5%" if preset_id=="michelle_soft" else "+0%",
            "pitch":"+2Hz" if preset_id=="emma_energetic" else "+0Hz", "desc":f"{gender} · English · {voice.split('-')[1]} accent"})
VOICE_PRESETS += [
    {"id":"neerja_hinglish","name":"Neerja · Hinglish","voice":"en-IN-NeerjaExpressiveNeural","gender":"Female","language":"Hinglish","rate":"+0%","pitch":"+0Hz","desc":"Hindi and English mixed conversation"},
    {"id":"swara_hindi","name":"Swara · Hindi","voice":"hi-IN-SwaraNeural","gender":"Female","language":"Hindi","rate":"+0%","pitch":"+0Hz","desc":"Hindi conversation"},
    {"id":"rvc_custom","name":"Custom RVC","voice":"rvc","gender":"Custom","language":"English","rate":"+0%","pitch":"+0Hz","desc":"Imported voice model"},
]

def voice_language(preset_id):
    return next((p['language'] for p in VOICE_PRESETS if p['id']==preset_id), 'English')

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
