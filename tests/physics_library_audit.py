"""Audit the physics rigs of every PMX model in Sakura's library.

The runtime physics engine (static/js/model-physics.js) picks simulated
bones from geometry.userData.MMD.bones[].rigidBodyType — the per-bone
maximum rigid-body type MMDLoader computes from the PMX rigid bodies
(0 = static collider, 1/2 = dynamic). This script parses that same data
straight from each .pmx file, without rendering, to answer library-wide
coverage questions: how many models carry a usable physics rig, how many
fall back to bone-name detection, and how many have no physics bones at
all ("No physics available").

Validated against live runtime results: Barbara 160 bones / 22 chains,
TDA Yumeko 94 / 19.

Usage: venv/Scripts/python.exe tests/physics_library_audit.py [--limit N]
"""
import argparse
import json
import re
import struct
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
MODELS = BASE / 'models'
OUT = BASE / 'audit-results' / 'physics-audit.json'

# Same patterns as model-physics.js FALLBACK_PATTERNS (checked in order).
FALLBACK_PATTERNS = [
    ('breast', re.compile(r'胸|乳|おっぱい|bust|breast|boob|oppai', re.I)),
    ('hair', re.compile(r'髪|发|髮|ツインテール|ツインテ|おさげ|ポニーテール|アホ毛|三つ編み|hair|ponytail|twintail|pigtails|ahoge|braid', re.I)),
    ('skirt', re.compile(r'スカート|裾|フリル|マフラー|裙|skirt|frill|muffler|scarf', re.I)),
    ('other', re.compile(r'リボン|尻尾|しっぽ|羽|袖|ネクタイ|ベルト|ポンポン|ribbon|tail|wing|sleeve|tie|belt|pompom', re.I)),
]

# Bones the viewer animates itself; the runtime fallback never picks these.
RESERVED = {
    '上半身', '上半身2', 'spine', 'Spine', 'chest', 'Chest', '頭', 'head', 'Head',
    '首', 'neck', 'Neck', '左目', '右目', 'LeftEye', 'RightEye', 'eye.L', 'eye.R',
    '左手首', '右手首', 'LeftHand', 'RightHand', 'hand.L', 'hand.R',
    '左腕', '右腕', 'LeftArm', 'RightArm', 'upper_arm.L', 'upper_arm.R',
    '左ひじ', '右ひじ', 'LeftForeArm', 'RightForeArm', 'forearm.L', 'forearm.R',
}


class Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def skip(self, n):
        self.pos += n

    def u8(self):
        v = self.data[self.pos]
        self.pos += 1
        return v

    def u16(self):
        v = struct.unpack_from('<H', self.data, self.pos)[0]
        self.pos += 2
        return v

    def i32(self):
        v = struct.unpack_from('<i', self.data, self.pos)[0]
        self.pos += 4
        return v

    def index(self, size):
        if size == 1:
            v = struct.unpack_from('<b', self.data, self.pos)[0]
        elif size == 2:
            v = struct.unpack_from('<h', self.data, self.pos)[0]
        else:
            v = struct.unpack_from('<i', self.data, self.pos)[0]
        self.pos += size
        return v

    def text(self, encoding):
        length = self.i32()
        raw = self.data[self.pos:self.pos + length]
        self.pos += length
        return raw.decode('utf-16-le' if encoding == 0 else 'utf-8', errors='replace')

    def skip_text(self):
        length = self.i32()
        self.pos += length


def parse_pmx(path):
    data = path.read_bytes()
    r = Reader(data)
    if data[:4] != b'PMX ':
        raise ValueError('not a PMX file')
    r.skip(4)
    version = struct.unpack_from('<f', data, r.pos)[0]
    r.skip(4)
    globals_count = r.u8()
    if globals_count != 8:
        raise ValueError(f'unexpected globals count {globals_count}')
    encoding = r.u8()
    additional_uv = r.u8()
    sizes = {'vertex': r.u8(), 'texture': r.u8(), 'material': r.u8(),
             'bone': r.u8(), 'morph': r.u8(), 'rigidbody': r.u8()}

    for _ in range(4):  # model name/comment textbufs
        r.skip_text()

    # Vertices: constant stride per vertex, bulk-skipped.
    vertex_count = r.i32()
    weight_sizes = {0: sizes['bone'], 1: 2 * sizes['bone'] + 4,
                    2: 4 * sizes['bone'] + 16, 3: 2 * sizes['bone'] + 40,
                    4: 4 * sizes['bone'] + 16}
    vertex_stride = 32 + additional_uv * 16 + 4  # pos+normal+uv, edge scale
    # Weight layout varies per vertex, so walk them (cheap, no decode).
    for _ in range(vertex_count):
        r.skip(32 + additional_uv * 16)
        wtype = r.u8()
        r.skip(weight_sizes[wtype])
        r.skip(4)

    # Faces: uniform index size, bulk-skip.
    face_count = r.i32()
    r.skip(face_count * sizes['vertex'])

    # Textures.
    for _ in range(r.i32()):
        r.skip_text()

    # Materials (full walk; sizes depend on toon flags).
    for _ in range(r.i32()):
        for _ in range(2):  # name + english name
            r.skip_text()
        r.skip(44)  # diffuse 4f + specular 3f + strength + ambient 3f
        r.u8()      # flags
        r.skip(20)  # edge color 4f + edge size
        r.skip(sizes['texture'] * 2)  # diffuse + sphere texture indices
        r.u8()      # sphere mode
        if r.u8() == 0:
            r.skip(sizes['texture'])  # toon texture index
        else:
            r.u8()                    # shared toon index
        r.skip_text()  # memo
        r.i32()        # surface count

    # Bones (the section the solver's bone set comes from).
    bone_count = r.i32()
    bones = []
    for i in range(bone_count):
        name = r.text(encoding)
        r.skip_text()  # english name
        position = struct.unpack_from('<3f', data, r.pos)  # offset from parent
        r.skip(12)
        parent = r.index(sizes['bone'])
        r.i32()        # layer
        flags = r.u16()
        if flags & 0x0001:
            r.skip(sizes['bone'])  # tail as bone index
        else:
            r.skip(12)             # tail as offset
        if flags & 0x0100 or flags & 0x0200:
            r.skip(sizes['bone'] + 4)  # grant parent + rate
        if flags & 0x0400:
            r.skip(12)             # fixed axis
        if flags & 0x0800:
            r.skip(24)             # local axes
        if flags & 0x2000:
            r.i32()                # external parent key (0x1000 = after physics, no data)
        if flags & 0x0020:         # IK
            r.skip(sizes['bone'])  # target
            r.skip(8)              # loops + angle limit
            for _ in range(r.i32()):
                r.skip(sizes['bone'])
                link_flags = r.u8()
                if link_flags & 0x0001:
                    r.skip(24)     # angle limit: lower + upper vec3
        bones.append({'name': name, 'parent': parent, 'pos': position})

    # Morphs (walked only to reach the rigid-body section).
    morph_count = r.i32()
    for _ in range(morph_count):
        r.skip_text()
        r.skip_text()
        r.u8()   # category
        morph_type = r.u8()
        offset_count = r.i32()
        if morph_type == 0:    # group: index + float ratio
            r.skip(offset_count * (sizes['morph'] + 4))
        elif morph_type == 1:  # vertex
            r.skip(offset_count * (sizes['vertex'] + 12))
        elif morph_type == 2:  # bone
            r.skip(offset_count * (sizes['bone'] + 28))
        elif morph_type <= 7:  # uv / additional uv
            r.skip(offset_count * (sizes['vertex'] + 16))
        elif morph_type == 8:  # material: index + mode + 64 bytes of factors + 4 blend flags
            r.skip(offset_count * (sizes['material'] + 69))
        else:
            raise ValueError(f'unknown morph type {morph_type}')

    # Display frames (between morphs and rigid bodies in the PMX layout).
    for _ in range(r.i32()):
        r.skip_text()
        r.skip_text()
        r.u8()   # special frame flag
        element_count = r.i32()
        for _ in range(element_count):
            element_type = r.u8()  # 0 = bone, 1 = morph
            r.skip(sizes['bone'] if element_type == 0 else sizes['morph'])

    # Rigid bodies: the physics rig itself.
    rigid_count = r.i32()
    body_type_per_bone = {}
    dynamic_bodies = 0
    for _ in range(rigid_count):
        r.skip_text()
        r.skip_text()
        bone_index = r.index(sizes['bone'])
        r.u8()   # collision group
        r.u16()  # no-collision mask
        r.u8()   # shape
        r.skip(36)  # size 3f + position 3f + rotation 3f
        r.skip(20)  # mass + 4 damping/restitution/friction floats
        mode = r.u8()
        if bone_index >= 0 and bone_index < bone_count:
            previous = body_type_per_bone.get(bone_index, -1)
            body_type_per_bone[bone_index] = max(previous, mode)
            if mode >= 1:
                dynamic_bodies += 1

    # Mirror the runtime: dynamic bones (max body type 1/2), skipping
    # zero-length bones, chains = roots whose parent is not simulated.
    physics = {i for i, t in body_type_per_bone.items() if t >= 1}
    zero_length = sum(1 for i in physics if max(map(abs, bones[i]['pos'])) < 1e-6)
    simulated = [i for i in sorted(physics) if max(map(abs, bones[i]['pos'])) >= 1e-6]
    chains = sum(1 for i in simulated if bones[i]['parent'] not in physics)
    categories = {}
    for i in simulated:
        for category, pattern in FALLBACK_PATTERNS:
            if pattern.search(bones[i]['name']):
                categories[category] = categories.get(category, 0) + 1
                break
        else:
            categories['other'] = categories.get('other', 0) + 1

    # Name-fallback coverage, as the runtime would compute it for models
    # with no dynamic bodies at all.
    fallback = {}
    for i, bone in enumerate(bones):
        if bone['name'] in RESERVED:
            continue
        for category, pattern in FALLBACK_PATTERNS:
            if pattern.search(bone['name']):
                fallback[category] = fallback.get(category, 0) + 1
                break

    return {
        'bones': len(simulated),
        'zeroLengthPhysicsBones': zero_length,
        'chains': chains,
        'dynamicBodies': dynamic_bodies,
        'categories': categories,
        'fallbackIfNoRig': fallback,
        'boneCount': bone_count,
    }


def audit_vrm(path):
    """VRM physics = the runtime's spring-bone passthrough. Detect the
    spring-bone extension in the GLB JSON chunk."""
    data = path.read_bytes()
    if data[:4] != b'glTF':
        return {'source': 'unknown', 'bones': 0}
    length = struct.unpack_from('<I', data, 12)[0]
    json_chunk = data[20:20 + length].decode('utf-8', errors='replace')
    has_vrm1 = 'VRMC_springBone' in json_chunk
    has_vrm0 = '"secondaryAnimation"' in json_chunk
    if has_vrm1 or has_vrm0:
        return {'source': 'vrm springbone', 'bones': None}
    return {'source': 'none', 'bones': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()

    pmx_files = sorted(MODELS.glob('pmx/**/*.pmx'))
    if args.limit:
        pmx_files = pmx_files[:args.limit]
    vrm_files = sorted(MODELS.glob('vrm/**/*.vrm'))

    results = []
    errors = []
    for i, path in enumerate(pmx_files):
        rel = path.relative_to(MODELS).as_posix()
        try:
            info = parse_pmx(path)
            results.append({'path': rel, **info})
        except Exception as exc:  # malformed or exotic export
            errors.append({'path': rel, 'error': f'{type(exc).__name__}: {exc}'})
        if (i + 1) % 100 == 0:
            print(f'  {i + 1}/{len(pmx_files)} parsed', flush=True)

    vrm_results = []
    for path in vrm_files:
        try:
            vrm_results.append({'path': path.relative_to(MODELS).as_posix(),
                                **audit_vrm(path)})
        except Exception as exc:
            errors.append({'path': path.relative_to(MODELS).as_posix(),
                           'error': f'{type(exc).__name__}: {exc}'})

    rigged = [r for r in results if r['bones'] > 0]
    fallback_only = [r for r in results if r['bones'] == 0 and any(r['fallbackIfNoRig'].values())]
    no_physics = [r for r in results if r['bones'] == 0 and not any(r['fallbackIfNoRig'].values())]

    category_totals = {}
    for r in rigged:
        for category, count in r['categories'].items():
            category_totals[category] = category_totals.get(category, 0) + count

    bone_counts = sorted(r['bones'] for r in rigged)
    summary = {
        'pmxTotal': len(results),
        'pmxWithRigPhysics': len(rigged),
        'pmxFallbackOnly': len(fallback_only),
        'pmxNoPhysics': len(no_physics),
        'parseErrors': len(errors),
        'categoryTotals': category_totals,
        'smallestRig': bone_counts[0] if bone_counts else None,
        'medianRig': bone_counts[len(bone_counts) // 2] if bone_counts else None,
        'largestRig': bone_counts[-1] if bone_counts else None,
        'vrmTotal': len(vrm_results),
        'vrmWithSpringbone': sum(1 for v in vrm_results if v['source'] == 'vrm springbone'),
        'vrmNoSpringbone': sum(1 for v in vrm_results if v['source'] == 'none'),
    }
    report = {
        'summary': summary,
        'noPhysics': [r['path'] for r in no_physics],
        'fallbackOnly': [{'path': r['path'], 'categories': r['fallbackIfNoRig']} for r in fallback_only],
        'errors': errors,
        'vrm': vrm_results,
        'smallestRigs': sorted([{'path': r['path'], 'bones': r['bones'], 'chains': r['chains']}
                                for r in rigged], key=lambda x: x['bones'])[:15],
        'models': results,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f'\nFull report: {OUT}')
    if errors:
        print(f'{len(errors)} parse errors, first 5:')
        for error in errors[:5]:
            print(f"  {error['path']}: {error['error']}")
    if no_physics:
        print(f'{len(no_physics)} models with no physics bones, first 10:')
        for r in no_physics[:10]:
            print(f"  {r['path']}")


if __name__ == '__main__':
    main()
