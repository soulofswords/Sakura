"""Optional installer entry point for Sakura's CUDA inference runtime."""
import json
from pathlib import Path
from config import BASE_DIR

from inference_engines import install


def main():
    root = BASE_DIR / 'desktop-profile' / 'agent-local-ai'
    def progress(value):
        print(json.dumps({'message': 'Downloading and verifying CUDA inference runtime…', 'percent': value}), flush=True)
    try:
        install(root, 'llama.cpp', 'cuda', progress)
        print(json.dumps({'message': 'CUDA inference runtime installed. Select CUDA or Auto in Agent Local AI.', 'percent': 100}), flush=True)
        return 0
    except Exception as error:
        print(json.dumps({'message': str(error) if isinstance(error, ValueError) else 'CUDA download failed. You can retry from Agent Local AI.'}), flush=True)
        return 1
