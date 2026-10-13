"""Remove only corrupt optional PNG metadata; preserve pixel chunks and originals."""
import json
import shutil
import struct
import zlib
from pathlib import Path
from PIL import Image
root=Path('audit-results/full-library-2026-10-09')
report=json.loads((root/'assets.json').read_text(encoding='utf-8'))
fixed=[]
for item in report['pmx']:
    for texture in item['invalid']:
        file=Path('models')/texture['path']
        data=file.read_bytes()
        if data[:8]!=b'\x89PNG\r\n\x1a\n':
            continue
        chunks=[];removed=[];offset=8
        while offset+12<=len(data):
            size=struct.unpack_from('>I',data,offset)[0]
            kind=data[offset+4:offset+8]
            if offset+12+size>len(data):
                raise ValueError(f'Truncated PNG: {file}')
            crc=struct.unpack_from('>I',data,offset+8+size)[0]
            actual=zlib.crc32(data[offset+4:offset+8+size])&0xffffffff
            if crc!=actual:
                if kind not in (b'iCCP',b'tEXt',b'zTXt',b'iTXt'):
                    raise ValueError(f'Corrupt image data: {file}')
                removed.append(kind.decode())
            else:
                chunks.append(data[offset:offset+12+size])
            offset+=12+size
        if removed:
            backup=root/'original-textures'/texture['path']
            backup.parent.mkdir(parents=True,exist_ok=True)
            if not backup.exists():
                shutil.copy2(file,backup)
            file.write_bytes(data[:8]+b''.join(chunks))
            with Image.open(file) as image:
                image.load()
            fixed.append({'path':texture['path'],'removedMetadata':removed,'backup':str(backup)})
(root/'texture-repairs.json').write_text(json.dumps(fixed,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Repaired {len(fixed)} PNGs; pixel data preserved')
