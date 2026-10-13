# Sakura on Apple Silicon

This source now has macOS platform paths for M1 and newer, targeting macOS Sonoma 14 or newer. It has not been run on a real Mac yet. Windows regression tests and mocked macOS boundary tests passed; this is not a signed/notarized Mac app release.

Verification on 2026-10-09: 126 Python tests plus 3 subtests passed; 22 frontend regression suites passed; Python/JavaScript syntax and Bash syntax for all three Mac scripts passed. One existing Starlette/httpx deprecation warning remains. No Windows runtime, model, voice, key or user setting was deleted or replaced.

## First launch

1. Copy the Sakura source folder to a writable location on your Mac. Keep `static/`, `personality/`, `launcher/`, `models/`, `voices/`, `rvc-assets/` and `llm-models/` as needed. Windows executables and Windows Python environments cannot run on macOS; you do not need to copy those runtime folders. No files are removed by these setup scripts.
2. Install native ARM64 Homebrew from https://brew.sh. Run Terminal without Rosetta.
3. In Terminal, change to the copied Sakura folder and run `bash setup-macos.command`. This installs native Python 3.12, PortAudio, FFmpeg, Ollama and a new `.venv-macos` environment.
4. Run `bash run-macos.command`. After setup, `run-macos.command` can also be opened in Finder. For initial full-size model library view, run `bash run-macos.command --library`. The existing window controls switch between library and companion.

Use the launch popup to select Local LLM, Gemini, or tracking-only VTuber mode. The Windows encrypted Gemini key cannot be transferred: enter your key again on the Mac. It is stored in Apple Keychain, not in the Windows key file. If a copied settings file contains a Windows local-model-folder path, choose the Mac `llm-models/` folder in Settings → AI. Model blobs/manifests are data and can be copied without redownloading Qwen. An already-running Ollama system service is reused; configure its models folder separately if it is serving a different store.

## Mac behavior

- Local Qwen uses the native macOS Ollama executable and its Apple Metal backend. The Windows CUDA/Vulkan runtime is never launched on Mac.
- The Qt/Chromium viewer renders PMX and VRM, retaining materials, Bullet physics and fallback detection. No Direct3D 11 flag is forced on Mac.
- Built-in voices and CPU speech recognition use the native environment. FFmpeg handles browser microphone recordings.
- Microphone, Camera and Screen Recording permissions may be requested by macOS. Grant only the permissions for features you enable in System Settings → Privacy & Security. The permission entry may appear as Python or Terminal for this source launcher. Restart after changing permissions if macOS requires it.
- Ctrl+Shift+T uses a global keyboard listener. Accessibility and Input Monitoring permission may be required for Python/Terminal. Click-through is deliberately blocked unless the listener is available, so an unclickable window always has a recovery shortcut.
- Mouse following uses Quartz coordinates. Screen capture uses the main display and normalizes Retina pixels before masking the companion from the AI's image.
- Browser launch commands use macOS `open`; Steam and Epic launch paths use `.app` bundles and their URI handlers. Game detection recognizes a foreground game in known library folders and keeps that session until its process exits. Windows anti-cheat/process enumeration features do not apply on Mac; background game discovery is currently Windows-only.
- Closing Sakura kills only worker process groups it started. Existing system Ollama services are not terminated.
- PMX Editor itself remains Windows-only. Its buttons are hidden on Mac, and source models can be edited on Windows then copied/reloaded.

## Optional RVC

The base installer does not install the large legacy RVC stack. Built-in voices work without it. For custom RVC, a separate experimental CPU installer is provided:

`bash setup-rvc-macos.command`

This requires native ARM64 Python 3.10 and Apple command line tools (`xcode-select --install`). If Python 3.10 is not in PATH, set `SAKURA_RVC_PYTHON` to its full executable path. It creates `rvc-mac-runtime/` and builds legacy fairseq from source; it does not reuse the Windows wheel or ComfyUI redirect. RVC is forced to float32 CPU, including pitch extraction. The installer and conversion still need verification on an actual Mac; MPS GPU RVC is not claimed.

## Verification still needed on Mac

Run the full test suite from `.venv-macos`, then check native window launch, library/companion transitions, PMX/VRM rendering, microphone and camera permissions, screen capture on Retina, Ctrl+Shift+T recovery, actual Qwen Metal inference, and optional RVC audio conversion. A distributable signed `.app` must be built and tested on macOS; the Windows `.exe` is not a Mac launcher.

References: https://docs.ollama.com/macos (macOS 14+, Apple M-series support), https://github.com/ollama/ollama/blob/main/docs/gpu.mdx (Metal), https://pywebview.flowrl.com/guide/ (macOS and Qt support).
