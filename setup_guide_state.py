"""Installation-local onboarding flags, independent of changing loopback ports."""
import json
from pathlib import Path
from atomic_state import state_lock, atomic_text

EDITIONS = {'companion', 'vtuber', 'agent'}

def seen(root, edition, mark=False):
    if edition not in EDITIONS:
        raise ValueError('Unknown setup guide.')
    path = Path(root) / 'desktop-profile' / 'setup-guide-seen.json'
    with state_lock(path):
        try:
            saved = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(saved, dict):saved = {}
        except (OSError, ValueError):saved = {}
        if mark:
            saved[edition] = True
            atomic_text(path, json.dumps(saved))
        return saved.get(edition) is True
