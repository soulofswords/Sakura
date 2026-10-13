#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
    echo "Use a native Apple Silicon Mac (M1 or newer), not Rosetta." >&2
    exit 1
fi
major="$(sw_vers -productVersion | cut -d. -f1)"
if (( major < 14 )); then
    echo "Sakura's local Ollama setup requires macOS Sonoma 14 or newer." >&2
    exit 1
fi
if ! command -v brew >/dev/null 2>&1; then
    echo "Install Homebrew from https://brew.sh, then run this setup again." >&2
    exit 1
fi
brew install python@3.12 portaudio ffmpeg
python="$(brew --prefix python@3.12)/bin/python3.12"
"$python" -c 'import platform; assert platform.machine() == "arm64", "Native ARM64 Python required"'
"$python" -m venv .venv-macos
.venv-macos/bin/python -m pip install --upgrade pip
.venv-macos/bin/python -m pip install -r requirements-macos.txt
.venv-macos/bin/python -c 'import app, webview; from PySide6 import QtWebEngineWidgets; import keyring, Quartz; print("Sakura imports OK")'
chmod +x run-macos.command setup-rvc-macos.command
echo "Ready. Open run-macos.command. Copy models/, voices/, and llm-models/ to this folder as needed."
