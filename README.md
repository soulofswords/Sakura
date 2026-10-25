# Sakura

Sakura is a desktop character companion and webcam VTuber application under active development. The source includes separate Companion and VTuber product launchers, a local web interface, and Windows/Apple Silicon packaging tools.

## Features

- PMX, VRM and Live2D model loading, expressions and model settings.
- Webcam face and optional hand tracking, physics, and streaming controls.
- Companion conversations through selected cloud providers or an optional local Qwen model, with provider-bound model discovery and small API generation checks.
- Sakura Mobile: separate PC-controller and phone-local model/chat workflows, with authenticated model transfer and saved phone models.
- Built-in speech voices and optional RVC voice conversion.
- Optional NVIDIA Broadcast camera selection and NVIDIA AR SDK setup guidance. Native NVIDIA AR facial inference is not connected yet.

See [15 October 2026 update notes](docs/UPDATE-2026-10-15.md) for mobile setup, cloud diagnostics, animation, rendering and installer changes, including testing limitations. Source stays private; compiled/obfuscated tester builds are published separately in [Sakura Downloads](https://github.com/soulofswords/Sakura-Downloads/releases/tag/windows-beta-2026-10-25).

## Run from source on Windows

Install Python 3.12 and Git, clone this repository, and run:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe desktop.py
```

Use `run_gui.bat` for the web interface. Import your own character models using the application. Character artwork, voice weights, local LLM weights, virtual environments and private configuration are deliberately excluded from this repository. Add a Gemini key in the application or choose the optional local-model download; no LLM download is required for webcam-only tracking.

For Apple Silicon setup, see [docs/MACOS.md](docs/MACOS.md).

## Development and packaging

Application code is in the root Python modules and `static/`. Native launcher and installer sources are in `launcher/`; build scripts and validation tools are in `tools/` and `tests/`.

`tools/build-split-installers.py` builds the separate product packages. Packaging needs local Python dependencies and packaging prerequisites; generated installers, build caches and reports are not stored in Git. Some model validation scripts require locally imported models.

Third-party libraries retain their own licenses and distribution terms. A private repository does not grant redistribution rights to imported models, artwork, voice weights or SDKs.

## Feedback

This app is currently under development. Feedback is welcome through [Discord](https://discord.gg/kgxeMRFWDw).

Latest release: [25 October 2026 Windows + Android beta](https://github.com/soulofswords/Sakura-Downloads/releases/tag/windows-beta-2026-10-25). See [release notes](docs/UPDATE-2026-10-25.md) and the separate [Companion](docs/user-guides/companion.md) / [VTuber](docs/user-guides/vtuber.md) guides for the current UI.
