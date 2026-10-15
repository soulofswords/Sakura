# Local Kokoro speech

Sakura uses Kokoro-82M v1.0 through the CPU ONNX runtime for its built-in voices. The default is Sakura · Heart. There are ten female English voices, ten male English voices, one Hindi voice and one Hinglish voice. Installed Windows voices and imported RVC voices remain separate choices.

Older saved Edge voice selections migrate to local replacements. Other preferences and imported models are retained. The new names describe actual Kokoro voices; they are not copies of Microsoft's Ava, Jenny or other cloud voices.

The verified runtime assets are stored in `kokoro-assets/`: approximately 121 MB combined. Current installers include these speech assets and their license notices, while excluding imported character models and RVC weights. The local developer editions share this folder. If the assets are missing, the first speech operation shows a preparation/download popup. It closes when initialization completes. Subsequent synthesis runs without network requests or an API key.

Speech is generated to a WAV file and played through Sakura's existing output device and lip-sync controls. Only one CPU synthesis job runs at a time, using up to four inference threads. Voice changes apply to the next reply; an in-progress reply retains its selected voice. RVC converts Kokoro base audio when an imported RVC voice is selected.

Hindi/Hinglish use the Hindi phonemizer and authored Hindi voices. Latin-script Hinglish pronunciation can vary, so sample generation does not guarantee native pronunciation for every mixed-language phrase. Kokoro does not provide voice cloning. GPU acceleration is not required.

Windows testing: all 22 presets generated distinct nonempty WAV files with network requests blocked after setup; Companion speech, voice previews and tracking-only Chat Reader endpoints returned valid audio. Native macOS hardware has not been tested.

Before creating a release, run `venv/Scripts/python.exe tools/install-kokoro.py` if the speech assets need downloading or verifying. The standard installer builder validates their sizes and SHA-256 hashes and includes Kokoro regression checks.

Upstream: [Kokoro model](https://huggingface.co/hexgrad/Kokoro-82M), [Kokoro ONNX runtime](https://github.com/thewh1teagle/kokoro-onnx). See the accompanying model/runtime license notices and the phonemizer/eSpeak licenses in their dependency packages.

Response latency: desktop listening submits speech after about 700 ms of silence. Companion chat prepares Kokoro concurrently with the AI request, warms its first inference, and plays short phrases while preparing the next phrase. AI generation, transcription and CPU synthesis still contribute latency; RVC adds conversion time.
