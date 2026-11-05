# Sakura

An open-source character companion, VTuber studio and approval-based desktop agent.

[Download Sakura 2.0](https://github.com/soulofswords/Sakura-Downloads/releases/tag/v2.0) · [Website](https://soulofswords.github.io/Sakura-website/) · [Companion guide](docs/user-guides/companion.md) · [VTuber guide](docs/user-guides/vtuber.md)

## Choose your experience

- **Companion:** talk or type to your character using a selected local or cloud AI model, with speech, expressions and optional screen/camera context.
- **VTuber:** animate PMX, VRM or Live2D characters with face and optional hand tracking. The standalone VTuber edition does not run the Companion chat/Agent LLM; chat reading and voice conversion are separate features.
- **Agent (inside Companion):** plan tasks with workspace file tools, terminal commands, browser tools, skills, automations and connected MCP services. Review actions using the configured access policy.
- **Sakura Mobile:** pair with your PC for tracking/control and model transfer, or use supported phone-local workflows.

Character controls include model import, materials/textures, expressions, physics and streaming/output settings. Optional integrations need compatible hardware, separately installed runtimes or your own service account. Code presence alone does not guarantee that a particular device or provider works.

## Run from source on Windows

Use Python 3.12 and Git:

```powershell
git clone https://github.com/soulofswords/Sakura.git
cd Sakura
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe desktop.py
```

The desktop entry point opens a native window. The UI/backend communicate through a local loopback server. `run_gui.bat` opens the browser interface instead.

Import your own models in the app. PMX and Live2D need their texture/assets folders; VRM uses a `.vrm` file. Add provider credentials in the app or install an optional local inference runtime/model. Webcam-only tracking does not require an LLM. Optional RVC dependencies are listed in `requirements-rvc.txt`.

Windows is the primary tested desktop target. [macOS notes](docs/MACOS.md) describe the separate Apple Silicon setup; build scripts alone are not a claim of a tested current macOS release.

## Source and development

This repository now includes **AI Companion/Agent source, VTuber source and Android source**. The public starting point incorporates the existing `release/companion-2.0` source snapshot. Unfinished local workspace changes are not silently included in this publication.

- Root Python modules: backend; `static/`: web UI/renderer; `android/`: mobile client.
- `launcher/`: Windows launchers/installers; `tools/`: packaging/checks; `docs/`: guides.
- Python checks: install `pytest`, then run `.\venv\Scripts\python.exe -m pytest tests/ -q`.
- Browser checks need Node.js and Playwright installed locally before running the relevant `tests/*.cjs` files. Some checks need Windows or local test assets.
- `tools/build-split-installers.py` builds the editions when its native/runtime prerequisites are present. Build output and personal configuration are not committed source dependencies.

Use [Sakura Downloads](https://github.com/soulofswords/Sakura-Downloads/releases) for current installers/APKs. Older illustrated guide screenshots may still carry their original version labels.

## Privacy and contributions

API keys, account sessions, MCP credentials, conversations, saved voice profiles, character libraries, RVC weights and LLM weights are **not included**. Configure your own accounts locally. Cloud-model sign-in does not expose the publisher's storage account.

Do not commit private configuration or recordings. See [SECURITY.md](SECURITY.md) for vulnerability reporting and [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidance.

## Licence

Copyright © 2026 Gaurang Bhogle and Sakura contributors. Sakura's original application source is available under **GNU GPL v3.0**, with the narrow optional Live2D integration permission in [LICENSE-EXCEPTIONS.md](LICENSE-EXCEPTIONS.md). See [LICENSE](LICENSE).

Third-party libraries retain their original licences. Live2D Cubism Core remains proprietary and is **not** relicensed under GPL. Imported artwork, voices, models, SDKs and services retain their own terms. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Feedback: [GitHub issues](https://github.com/soulofswords/Sakura/issues) or [Discord](https://discord.gg/kgxeMRFWDw).
