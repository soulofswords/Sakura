#!/bin/bash
# Optional legacy RVC stack: isolated CPU runtime, requires Python 3.10.
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
    echo "Native Apple Silicon macOS required." >&2
    exit 1
fi
python="${SAKURA_RVC_PYTHON:-python3.10}"
"$python" -c 'import sys,platform; assert sys.version_info[:2] == (3,10) and platform.machine() == "arm64", "Native Python 3.10 required for legacy fairseq"'
if ! xcode-select -p >/dev/null 2>&1; then
    echo "Install Apple command line tools (xcode-select --install), then retry." >&2
    exit 1
fi
"$python" -m venv rvc-mac-runtime
rvc-mac-runtime/bin/python -m pip install 'pip==23.3.2' 'setuptools<70' wheel 'Cython<3' 'numpy==1.26.4'
rvc-mac-runtime/bin/python -m pip install 'torch==2.4.1' 'torchaudio==2.4.1'
rvc-mac-runtime/bin/python -m pip install --no-build-isolation 'fairseq==0.12.2'
rvc-mac-runtime/bin/python -m pip install 'rvc-python==0.1.5' --no-deps
rvc-mac-runtime/bin/python -m pip install librosa faiss-cpu ffmpeg-python loguru praat-parselmouth pyworld resampy soundfile torchcrepe sacrebleu bitarray av fastapi uvicorn python-multipart
rvc-mac-runtime/bin/python -c 'import rvc_service; print(rvc_service.health())'
echo "Optional Mac RVC CPU runtime installed. GPU RVC is not enabled on Mac."
