"""Publisher-side preview creation. Runtime textures are not character portraits."""
import json
from pathlib import Path
from PIL import Image, ImageOps


def live2d_preview(folder, destination):
    folder=Path(folder).resolve()
    textures=set()
    for descriptor in folder.rglob('*.model3.json'):
        try:
            data=json.loads(descriptor.read_text(encoding='utf-8-sig'))
            for texture in data.get('FileReferences',{}).get('Textures',[]):
                textures.add((descriptor.parent/texture).resolve())
        except (OSError,ValueError,TypeError):continue
    candidates=[]
    for path in folder.rglob('*'):
        if path.suffix.lower() not in ('.png','.jpg','.jpeg','.webp') or not path.is_file():continue
        if path.is_symlink() or not path.resolve().is_relative_to(folder) or path.resolve() in textures:continue
        relative=path.relative_to(folder)
        if any('texture' in part.lower() for part in relative.parts):continue
        preferred=any(word in path.stem.lower() for word in ('preview','thumbnail','portrait','cover','icon'))
        candidates.append((not preferred,len(relative.parts),path.as_posix(),path))
    for *_,path in sorted(candidates):
        try:
            with Image.open(path) as image:
                if image.width*image.height>25_000_000:continue
                thumbnail=ImageOps.contain(image.convert('RGBA'),(512,512))
                square=Image.new('RGBA',(512,512))
                square.alpha_composite(thumbnail,((512-thumbnail.width)//2,(512-thumbnail.height)//2))
                square.save(destination,format='WEBP',quality=88,method=6)
            return True
        except (OSError,ValueError,Image.DecompressionBombError):continue
    return False


def turntable_frames(frames,destination):
    """Encode a real rendered 360-degree loop, rather than rotating a flat portrait."""
    images=[]
    for frame in sorted(Path(frames).glob('frame-*.png')):
        with Image.open(frame) as image:images.append(image.convert('RGB').resize((384,384)))
    if len(images)<12:raise ValueError('Render at least 12 turntable frames first.')
    images[0].save(destination,format='WEBP',save_all=True,append_images=images[1:],
                   duration=125,loop=0,quality=80,method=4)
    if Path(destination).stat().st_size>8_000_000:
        Path(destination).unlink()
        raise ValueError('Turntable exceeds the preview size limit.')
