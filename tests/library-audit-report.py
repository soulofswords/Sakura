"""Merge the complete renderer audit and targeted retests without losing evidence."""
import json
from pathlib import Path

root = Path('audit-results/full-library-2026-10-09')
catalog = json.loads((root / 'catalog.json').read_text(encoding='utf-8'))['models']
by_path = {}
for folder in ['part0', 'part1', 'dds-final', 'miku-final']:
    file = root / folder / 'results.json'
    if not file.exists():
        continue
    for result in json.loads(file.read_text(encoding='utf-8')):
        result['evidence'] = f'{folder}/results.json'
        for field in ['preview', 'previewFull']:
            if result.get(field):
                result[field] = f'{folder}/previews/{result[field]}'
        by_path[result['path']] = result
results = sorted(by_path.values(), key=lambda result: result['index'])
(root / 'final-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
assets = json.loads((root / 'assets.json').read_text(encoding='utf-8'))
missing = json.loads((root / 'missing-diffuse.json').read_text(encoding='utf-8'))
missing = [item for item in missing if item['missingDiffuse'] or item['missingOther']]
failures = [item for item in results if not item['ok']]
unchecked = [item['path'] for item in catalog if item['path'] not in by_path]
lines = [
    '# Model rendering audit — 9 October 2026', '',
    f"Checked {len(results)} of {len(catalog)} catalog entries: "
    f"{sum(item['ok'] for item in results)} rendering passes, {len(failures)} failures.", '',
    'The catalog contains 855 PMX and 7 VRM files, including weapons, accessories, base meshes, and backup variants. No Live2D models are currently uploaded.', '',
    'Each file was loaded through the running app’s asset server and actual Three.js ModelViewer in private GPU browser contexts. Checks cover JavaScript errors, WebGL context loss, visible pixels in portrait and desktop framing, textures, and geometry. Non-sensitive preview sheets were visually reviewed. Sensitive folders were tested privately without saved previews or changes to the visible companion.', '',
    '## Repairs applied', '',
    '- Added DDS decoding and image-signature detection, including safe neutral-image fallbacks for absent DDS files.',
    '- Wait for image decoding before preparing materials; preserve alpha cutouts with depth writes so hair and eye overlays render correctly.',
    '- Frame visible geometry rather than hidden helper meshes; use the head bone for portrait framing and fit full geometry in desktop mode.',
    '- Sanitize extreme or nonfinite vertices and morph positions in memory, preserving the original PMX files.',
    '- Removed corrupt PNG color-profile metadata from two Nekopara highlight textures. Original files are preserved under original-textures; pixel data is unchanged.', '',
    '## Remaining asset problems', '',
    f"{sum(bool(item['missing']) for item in assets['pmx'])} PMX entries reference absent texture files: "
    f"{sum(bool(item['missingDiffuse']) for item in missing)} need diffuse textures; "
    f"{sum(not item['missingDiffuse'] for item in missing)} lack only optional sphere/highlight maps. "
    'Neutral fallbacks let these files load, but cannot reconstruct missing artwork. Restore the original model package to obtain the intended colors.', '',
    f"All PMX files parsed; {sum(bool(item['badVertices']) for item in assets['pmx'])} source files contain extreme/nonfinite vertices, handled by the renderer. "
    f"Bad face-index packages: {sum(bool(item['badFaces']) for item in assets['pmx'])}. "
    f"Unreadable referenced texture packages after repair: {sum(bool(item['invalid']) for item in assets['pmx'])}.", '',
    'Passing a render check means the file loads and produces visible geometry, not that its appearance exactly matches the author’s reference or that every animation is clipping-free. Small contact-sheet previews and neutral lighting cannot certify detailed rigging, physics, or every pose.', '',
    '## Visual exceptions that still need attention', '',
    '- Maria Campbell (index 224): face/body appear nearly black. Its sphere-map reference resolves to a dark Skin.bmp; compare with the author’s reference before changing the material.',
    '- Short Kimono Meiko and Summer Bikini Meiko (indices 72–73): eye interiors look blank/dark despite available texture references. These need a separate material/UV investigation.',
    '- Honkai Sakura Memento and its small variant (indices 554–555): dark eye interiors in the preview; needs comparison against the original model before correction.',
    '- Several Luka/Kafka backup variants have uneven or absent colors; missing referenced maps are listed below.',
    '- Miku Elegant Princess / TDA Eternal Brilliance (index 35) faces backward in its authored orientation. It loads, but its front is not presented by the default camera.',
    'Backup/base variants, flower-face variants, and standalone accessories may intentionally look incomplete. Masked characters and stylized shadow faces are not automatically recolored.', '',
    '## Render failures', '',
]
lines += [f"- `{item['path']}`: {item.get('error', 'Unknown error')}" for item in failures] or ['None in the completed checks.']
if unchecked:
    lines += ['', f'Incomplete: {len(unchecked)} entries still await rendering.']
lines += ['', '## Missing texture details', '', '| Model | Diffuse files | Optional maps | Missing paths |', '|---|---:|---:|---|']
for item in missing:
    paths = next((entry['missing'] for entry in assets['pmx'] if entry['path'] == item['path']), [])
    details = '<br>'.join(entry['path'].replace('|', '/') for entry in paths)
    lines.append(f"| {item['path'].replace('|', '/')} | {item['missingDiffuse']} | {item['missingOther']} | {details} |")
lines += ['', 'Evidence: final-results.json, assets.json, texture-repairs.json, and sheets/. Tests are repeatable using the scripts in tests/library-*.py and tests/full-library-render.cjs.']
(root / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(json.dumps({'checked': len(results), 'total': len(catalog), 'failed': len(failures), 'unchecked': len(unchecked)}))
