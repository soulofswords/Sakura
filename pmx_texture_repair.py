"""Find decodable, unambiguous copies of a PMX texture inside its own package.

No image or PMX bytes are changed. Callers save per-material path overrides.
"""
from pathlib import Path
from PIL import Image


def inspect_image(file):
    try:
        if file.stat().st_size > 64 * 1024 * 1024:
            return {'status': 'unchecked', 'message': 'Image exceeds the 64 MB diagnostic limit.'}
        with Image.open(file) as image:
            if image.width * image.height > 16777216:
                return {'status': 'unchecked', 'message': 'Image exceeds the 4096 × 4096 diagnostic pixel limit.'}
            image.load()
            return {'status': 'ok', 'width': image.width, 'height': image.height}
    except (OSError, ValueError, Image.DecompressionBombError):
        return {'status': 'invalid', 'message': 'Image could not be decoded.'}


class PackageTextures:
    def __init__(self, package):
        self.root = Path(package).parent.resolve()
        self.inventory = None
        self.decoded = {}
        self.recovered = {}

    def inspect(self, file):
        file = Path(file).resolve()
        if file not in self.decoded:
            self.decoded[file] = inspect_image(file)
        return dict(self.decoded[file])

    def recover(self, reference):
        """Only one valid exact-basename copy qualifies; duplicates are ambiguous."""
        name = Path(reference.replace('\\', '/')).name.casefold()
        if name in self.recovered:
            return self.recovered[name]
        if self.inventory is None:
            self.inventory = {}
            for count, file in enumerate(self.root.rglob('*')):
                if count >= 10000:
                    raise ValueError('Model folder exceeds the 10,000-entry automatic repair limit.')
                if file.is_symlink() or '__MACOSX' in file.parts or file.name.startswith('._'):
                    continue
                if file.is_file() and file.resolve().is_relative_to(self.root):
                    self.inventory.setdefault(file.name.casefold(), []).append(file)
        matches = self.inventory.get(name, [])
        if len(matches) > 20:
            self.recovered[name] = None
            return None
        valid = [file for file in matches if self.inspect(file)['status'] == 'ok']
        if not valid:
            self.recovered[name] = None
            return None
        if len(valid) != 1:
            self.recovered[name] = None
            return None
        chosen = min(valid, key=lambda p: (len(p.parts), str(p).casefold()))
        result = {**self.inspect(chosen), 'status': 'repairable',
                  'resolved': chosen.relative_to(self.root).as_posix(),
                  'message': 'Found a decodable copy with the exact same filename inside this model folder.'}
        self.recovered[name] = result
        return result
