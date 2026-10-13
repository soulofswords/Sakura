#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
    echo "This launcher is for Apple Silicon macOS." >&2
    exit 1
fi
if [[ ! -x .venv-macos/bin/python ]]; then
    echo "Run setup-macos.command first." >&2
    exit 1
fi
export PATH="/opt/homebrew/bin:$PATH"
if [[ "${1:-}" == "--library" ]]; then
    export SAKURA_UPLOAD_UI=1
else
    unset SAKURA_UPLOAD_UI
fi
exec .venv-macos/bin/python startup_macos.py
