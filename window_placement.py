"""Compact Companion placement in display work-area coordinates."""
import json
import math
from pathlib import Path


def read_placement(path):
    try:
        value=json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(value,dict):return None
        if not all(type(value.get(k)) in (int,float) and math.isfinite(value[k]) for k in ('x','y','width','height')):return None
        if value['width']<=0 or value['height']<=0:return None
        return {k:int(value[k]) for k in ('x','y','width','height')}
    except (OSError,ValueError,OverflowError):return None


def compact_geometry(area,saved=None):
    width=min(area['width'],max(320,(saved or {}).get('width',460)))
    height=min(area['height'],max(400,(saved or {}).get('height',760)))
    right=area['x']+area['width']-width
    bottom=area['y']+area['height']-height
    return {'x':max(area['x'],min(right,(saved or {}).get('x',right-12))),
            'y':max(area['y'],min(bottom,(saved or {}).get('y',bottom-12))),
            'width':width,'height':height}


def save_placement(path,geometry):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(geometry),encoding='utf-8');temporary.replace(path)
