"""Compile and validate application bytecode without modifying editable sources."""
import argparse
import importlib.util
import json
import marshal
from pathlib import Path
import py_compile
import sys
import types

BASE = Path(__file__).resolve().parents[1]


def compile_application(output, source=BASE):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for file in sorted(Path(source).glob('*.py')):
        cache_name = Path(importlib.util.cache_from_source(file.name)).name
        target = output / '__pycache__' / cache_name
        target.parent.mkdir(exist_ok=True)
        py_compile.compile(str(file), cfile=str(target), dfile=file.name,
                           doraise=True, optimize=0,
                           invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)
        raw = target.read_bytes()
        if raw[:4] != importlib.util.MAGIC_NUMBER or int.from_bytes(raw[4:8], 'little') != 3:
            raise RuntimeError('Invalid bytecode header: ' + file.name)
        if raw[8:16] != importlib.util.source_hash(file.read_bytes()):
            raise RuntimeError('Bytecode source hash mismatch: ' + file.name)
        if not isinstance(marshal.loads(raw[16:]), types.CodeType):
            raise RuntimeError('Invalid bytecode body: ' + file.name)
        records.append((target, 'Sakura/__pycache__/' + cache_name))
    (output / 'bytecode-report.json').write_text(json.dumps({
        'python': sys.version.split()[0], 'cache_tag': sys.implementation.cache_tag,
        'mode': 'checked-hash; source retained; assertions enabled',
        'modules': [name for _, name in records]}, indent=2), encoding='utf-8')
    return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=BASE / 'tools' / 'bytecode-build')
    args = parser.parse_args()
    try:
        result = compile_application(args.output)
        (args.output / 'Bytecode-Errors.md').write_text('# Bytecode build\n\nPASS. No errors.\n', encoding='utf-8')
        print('PASS: compiled and validated', len(result), 'application modules into', args.output)
    except Exception as error:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / 'Bytecode-Errors.md').write_text('# Bytecode build errors\n\n' + str(error) + '\n', encoding='utf-8')
        raise
