"""Prepare and verify the local speech model before creating installers."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from kokoro_speech import prepare

if __name__=='__main__':
    print(prepare())
