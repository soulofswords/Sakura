"""
✨ Wake Word Detection — OpenWakeWord.
Optional module. Enable via WAKE_WORD_ENABLED in config.py.
"""
import numpy as np
import sounddevice as sd
from config import SAMPLE_RATE, WAKE_WORD, WAKE_WORD_THRESHOLD


class WakeWordDetector:
    def __init__(self):
        try:
            from openwakeword.model import Model

            # "hey_jarvis" is the closest built-in model
            self.model = Model(
                wakeword_models=["hey_jarvis"],
                inference_framework="onnx",
            )
            self.chunk_size = 1280  # ~80 ms at 16 kHz
            print(f"  ✨ Wake word ready — say \"{WAKE_WORD}\" to activate")
        except Exception as exc:
            print(f"  ⚠️  Wake word unavailable: {exc}")
            self.model = None

    def wait_for_wake_word(self) -> bool:
        """Block until the wake word is heard. Returns True on detection."""
        if self.model is None:
            return True  # skip if module failed to load

        print(f"\n💤 Say \"{WAKE_WORD}\" when you're ready…")

        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16"
        ) as stream:
            while True:
                data, _ = stream.read(self.chunk_size)
                audio = np.frombuffer(data, dtype=np.int16)
                prediction = self.model.predict(audio)

                for _name, score in prediction.items():
                    if score > WAKE_WORD_THRESHOLD:
                        print("✨ Wake word detected!")
                        self.model.reset()
                        return True
