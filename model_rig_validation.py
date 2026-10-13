"""Lightweight humanoid-rig checks for imported PMX and VRM packages."""
from __future__ import annotations

import json
import re
import struct


class _Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def take(self, size: int) -> bytes:
        if size < 0 or self.pos + size > len(self.data):
            raise ValueError('The PMX data is truncated or malformed.')
        value = self.data[self.pos:self.pos + size]
        self.pos += size
        return value

    def u8(self): return self.take(1)[0]
    def i32(self): return struct.unpack('<i', self.take(4))[0]
    def index(self, size): return struct.unpack('<b' if size == 1 else '<h' if size == 2 else '<i', self.take(size))[0]

    def count(self, what, limit=2_000_000):
        value = self.i32()
        if value < 0 or value > limit:
            raise ValueError(f'The PMX {what} count is invalid.')
        return value

    def text(self, encoding):
        length = self.count('text byte', len(self.data))
        try:
            return self.take(length).decode('utf-16-le' if encoding == 0 else 'utf-8', errors='replace')
        except (UnicodeError, ValueError):
            raise ValueError('The PMX contains an invalid text field.')


def pmx_bone_names(data: bytes) -> list[str]:
    """Read both Japanese and English PMX bone names without loading geometry."""
    r = _Reader(data)
    if r.take(4) != b'PMX ':
        raise ValueError('This is not a PMX file.')
    version = struct.unpack('<f', r.take(4))[0]
    if not 2.0 <= version <= 2.2:
        raise ValueError('This PMX version is not supported.')
    globals_count = r.u8()
    if globals_count != 8:
        raise ValueError('The PMX header is malformed.')
    encoding, additional_uv = r.u8(), r.u8()
    sizes = [r.u8() for _ in range(6)]
    vertex_size, texture_size, material_size, bone_size, morph_size, _rigid_size = sizes
    if encoding not in (0, 1) or additional_uv > 4 or any(size not in (1, 2, 4) for size in sizes):
        raise ValueError('The PMX index or encoding settings are invalid.')
    for _ in range(4): r.text(encoding)

    for _ in range(r.count('vertex')):
        r.take(32 + additional_uv * 16)
        weight_type = r.u8()
        layout = {0: bone_size, 1: bone_size * 2 + 4, 2: bone_size * 4 + 16,
                  3: bone_size * 2 + 40, 4: bone_size * 4 + 16}.get(weight_type)
        if layout is None: raise ValueError('The PMX contains an unknown vertex weight type.')
        r.take(layout + 4)
    r.take(r.count('face index') * vertex_size)
    for _ in range(r.count('texture')): r.text(encoding)
    for _ in range(r.count('material')):
        r.text(encoding); r.text(encoding)
        r.take(44); r.u8(); r.take(20 + texture_size * 2); r.u8()
        if r.u8() == 0: r.take(texture_size)
        else: r.u8()
        r.text(encoding); r.i32()

    names = []
    for _ in range(r.count('bone', 100_000)):
        names.extend((r.text(encoding), r.text(encoding)))
        r.take(12)
        r.index(bone_size); r.i32(); flags = struct.unpack('<H', r.take(2))[0]
        if flags & 0x0001: r.index(bone_size)
        else: r.take(12)
        if flags & (0x0100 | 0x0200): r.index(bone_size); r.take(4)
        if flags & 0x0400: r.take(12)
        if flags & 0x0800: r.take(24)
        if flags & 0x2000: r.i32()
        if flags & 0x0020:
            r.index(bone_size); r.take(8)
            for _ in range(r.count('IK link', 100_000)):
                r.index(bone_size); limit = r.u8()
                if limit & 0x01: r.take(24)
    return names


_ALIAS = {
    'hips': re.compile(r'^(?:センター|中|腰|下半身|骨盤|髋骨|髋|胯|hips?|pelvis|root(?:[._ -]?hip)?|lower[._ -]?body|bip\d* pelvis)$', re.I),
    'head': re.compile(r'^(?:頭|头|頭部|头部|head|bip\d* head)$', re.I),
    'torso': re.compile(r'^(?:上半身(?:[0-9]+)?|上身|胸|躯干|脊柱|spine(?:[._ -]?\d+)?|chest|torso|upper[._ -]?body|bip\d* spine(?:\d+)?)$', re.I),
    'left_arm': re.compile(r'^(?:左(?:肩|肩膀|上臂|手臂|小臂|前臂|腕|ひじ|肘|手)|(?:left|l)[._ -]?(?:shoulder|upper[._ -]?arm|arm|forearm|lower[._ -]?arm|hand|elbow)|(?:upper[._ -]?arm|arm|forearm|lower[._ -]?arm|hand|elbow)[._ -]?(?:left|l)|bip\d* l upperarm)$', re.I),
    'right_arm': re.compile(r'^(?:右(?:肩|肩膀|上臂|手臂|小臂|前臂|腕|ひじ|肘|手)|(?:right|r)[._ -]?(?:shoulder|upper[._ -]?arm|arm|forearm|lower[._ -]?arm|hand|elbow)|(?:upper[._ -]?arm|arm|forearm|lower[._ -]?arm|hand|elbow)[._ -]?(?:right|r)|bip\d* r upperarm)$', re.I),
    'left_leg': re.compile(r'^(?:左(?:足|脚|腿|大腿|小腿|脚|脚踝|もも|腿|ひざ|膝|足首)|(?:left|l)[._ -]?(?:upper[._ -]?leg|leg|thigh|lower[._ -]?leg|calf|foot|ankle)|(?:upper[._ -]?leg|leg|thigh|lower[._ -]?leg|calf|foot|ankle)[._ -]?(?:left|l)|bip\d* l thigh)$', re.I),
    'right_leg': re.compile(r'^(?:右(?:足|脚|腿|大腿|小腿|脚|脚踝|もも|腿|ひざ|膝|足首)|(?:right|r)[._ -]?(?:upper[._ -]?leg|leg|thigh|lower[._ -]?leg|calf|foot|ankle)|(?:upper[._ -]?leg|leg|thigh|lower[._ -]?leg|calf|foot|ankle)[._ -]?(?:right|r)|bip\d* r thigh)$', re.I),
}


def humanoid_bone_groups(names) -> set[str]:
    groups = set()
    for raw in names:
        name = re.sub(r'\s+', ' ', str(raw or '').strip())
        if not name: continue
        name = re.sub(r'^(?:mixamorig|armature|bip\d*)[._ :\-]*', '', name, flags=re.I)
        for group, pattern in _ALIAS.items():
            if pattern.fullmatch(name): groups.add(group)
    return groups


def validate_humanoid_names(names, label='Model'):
    groups = humanoid_bone_groups(names)
    required = {'hips', 'torso', 'head', 'left_arm', 'right_arm', 'left_leg', 'right_leg'}
    missing = required - groups
    if missing:
        pretty = {'hips':'hips/pelvis', 'torso':'spine/torso', 'head':'head',
                  'left_arm':'left arm', 'right_arm':'right arm', 'left_leg':'left leg', 'right_leg':'right leg'}
        raise ValueError(f'{label} does not have a recognizable humanoid skeleton (missing {", ".join(pretty[k] for k in sorted(missing))}). Import a humanoid PMX/VRM avatar.')
    return sorted(groups)


def validate_vrm_glb(data: bytes, label='Model'):
    if len(data) < 20 or data[:4] != b'glTF' or struct.unpack_from('<I', data, 4)[0] != 2 or struct.unpack_from('<I', data, 8)[0] != len(data):
        raise ValueError(f'{label} is not a valid binary VRM file.')
    offset = 12
    chunks = []
    while offset + 8 <= len(data):
        size, kind = struct.unpack_from('<II', data, offset); offset += 8
        if size > len(data) - offset: raise ValueError('VRM metadata is truncated.')
        chunks.append((kind, data[offset:offset + size])); offset += size
    json_chunk = next((chunk for kind, chunk in chunks if kind == 0x4E4F534A), None)
    if json_chunk is None: raise ValueError('VRM metadata is invalid.')
    document = json.loads(json_chunk.decode('utf-8-sig'))
    extensions = document.get('extensions', {})
    if 'VRMC_vrm' in extensions:
        human = extensions['VRMC_vrm'].get('humanoid', {}).get('humanBones', {})
        if not isinstance(human, dict):
            raise ValueError(f'{label} has invalid VRM 1 humanoid bone metadata.')
        entries = list(human.items())
    elif 'VRM' in extensions:
        human = extensions['VRM'].get('humanoid', {}).get('humanBones', [])
        # VRM 0.x uses [{bone: "hips", node: ...}, ...], whereas VRM 1.x
        # uses {hips: {node: ...}, ...}. Both are valid humanoid formats.
        if not isinstance(human, list) or any(not isinstance(bone, dict) for bone in human):
            raise ValueError(f'{label} has invalid VRM 0 humanoid bone metadata.')
        entries = [(bone.get('bone'), bone) for bone in human]
    else:
        raise ValueError(f'{label} is a GLB file, not a VRM avatar.')
    names = []
    nodes = document.get('nodes')
    for name, bone in entries:
        if not isinstance(name, str) or not isinstance(bone, dict):
            raise ValueError(f'{label} has invalid humanoid bone references.')
        node = bone.get('node')
        if not isinstance(node, int) or isinstance(node, bool) or node < 0 or (isinstance(nodes, list) and node >= len(nodes)):
            raise ValueError(f'{label} has an invalid node reference for humanoid bone {name}.')
        names.append(name)
    return validate_humanoid_names(names, label)
