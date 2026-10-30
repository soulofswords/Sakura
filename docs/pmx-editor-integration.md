# PMX Editor integration

On Windows, select a PMX model and click **PMX Editor** in either Sakura edition. The editor opens the exact source PMX file. Save changes in the editor and reload the model in Sakura to display them.

The local refresh and Windows installer preserve `tools/pmx-editor`, including the native executable, libraries, plugins and original documentation. Character and motion files from the editor folder are excluded from Windows packages. macOS does not package this Windows-only editor.

If the editor is missing, clicking the button opens a file picker for an existing `PmxEditor.exe` installation. The selected path is saved in user settings and reused. Keep its accompanying libraries in the same installation folder.

The source repository contains the integration code, not the third-party editor binaries. To build a Windows installer from source, provide a complete PMX Editor installation at `tools/pmx-editor` first. Build checks verify that the editor executable and library folder are installed in both editions.

This launches the native editor for comparison; it does not embed PmxView or make Sakura's renderer identical to PMX Editor.

## Snapshot and automatic texture-path repair

In Model Settings → Texture remapping, **Take snapshot and check textures**
captures Sakura's current model, launches PMX Editor with that exact PMX through
the existing native bridge, and checks every selected texture reference. After
confirmed mappings are saved, Sakura reloads the model and stores a second
snapshot with the report locally. Cancellation or editor-launch failure is
reported; file checks remain available in a browser or without the editor.

Every PMX check reloads the actual texture bytes using a fresh cache key, even
when all references are already valid on disk. This replaces stale neutral
fallbacks retained by a previously loaded model. The loaded-image check reads
MMD's non-enumerable map uniforms explicitly and reports diffuse fallbacks as
issues instead of treating their valid 1×1 white image as recovered artwork.

Before/after texture snapshots use portrait full-model framing while retaining
the current viewing direction. The main view's zoom, position, target and model
rotation are restored after reload. Rotate to the back or side before checking
to compare that same side in both images. The file/reference check covers all
materials regardless of which side is visible; rotating does not infer missing
artwork from pixels or limit repairs to visible surfaces.

If an image is missing or unreadable, automatic recovery accepts only one
decodable file with the exact same filename inside the selected model package.
It refuses multiple valid candidates and paths outside that package. The scan
is bounded to 10,000 entries and 20 same-name candidates. Existing image size
limits apply. Repairs use per-model, per-material `textures.json` overrides;
they do not rewrite PMX geometry, change artwork, or clear saved colour/alpha
edits. The snapshot report records unresolved references.

This includes sphere/shine (`.spa`, `.sph` and supported image files) and toon
references, not only the diffuse colour map. Additive sphere contribution is
composited independently of the diffuse texel, following the editor's own
disassembled shader branch recorded in [pmx-rea-verification.md](pmx-rea-verification.md);
multiply sphere contribution retains its multiplication mode. Browser
pixel tests cover both. Missing source maps and custom MME lighting are not
reconstructed from a picture of the model.

Opening the editor does not mean Sakura inspected its pixels or received an
editor diagnostic. There is currently no editor viewport-export bridge. This
flow repairs provable file/reference problems, not arbitrary differences in
lighting, custom effects, missing artwork or a user's saved appearance edits.

Verified with Silver Palace's Gratia and Traditional Miku **#2**. Gratia has no
unresolved references after its seven zero-filled textures were restored from
same-model originals. Miku #2 still reports three unresolved optional shading
references (`toon.bmp`, `pifu.spa`, `toon-DT.bmp`); no unrelated substitutes were
selected. Both runs physically launched PMX Editor with the correct model path
and produced Sakura snapshots. Native editor visual parity is not established
by these launch-and-file-check tests.


## Per-model appearance controls and separate snapshot

In Model Settings → Texture coloring → PMX appearance:

- Brightness adjusts the final rendered RGB without changing alpha.
- Ambient fill scales the authored flat fill; 100% preserves current defaults.
- Authored material tint controls the influence of the PMX diffuse colour.
- Toon shading blends between neutral shading and the authored toon ramp.
- Directional shading adds normal-dependent shading; 0% retains the flat anime presentation.
- Sphere / shine maps scales the authored additive/multiplicative sphere contribution.
- Specular highlights scales the bounded sharp highlight.
- Colour saturation controls the rendered colour intensity.

Each model has separate settings in the local app profile. Reset appearance
sliders restores the rendering defaults, leaving part colour/transparency,
texture remaps, gloss and bloom untouched. Settings apply on load, including
texture-diagnostic reloads. They also affect full-body snapshots and output.

The separate **Match appearance from PMX Editor** button now captures a real
reference through a temporary startup plugin in a separate editor process.
It exports the editor's Direct3D target, lighting settings and up to six large
opaque material references. A bounded material-by-material colour comparison
adjusts the saved sliders only if the score improves without worsening another
measured material. The direction remains aligned with the current model view.
Both the editor reference and Sakura result are shown and saved locally.
**Undo automatic appearance match** restores the previous slider values.

The texture-check button first repairs uniquely validated texture references,
reloads fresh GPU textures, then invokes the same appearance matcher on Windows.
It reports a failed reference capture instead of claiming the appearance matched.
The shared loader also rotates non-square toon maps into correctly swapped
canvas dimensions; previously 16×250 ramps became cropped black images.
This correction works without the editor on every affected PMX load.

Automatic reference capture requires a compatible, user-writable PMX Editor
installation and Windows .NET Framework 4.x compiler. The bridge has a timeout,
stops only its owned editor process and removes only its own hash-checked plugin.
It never saves the PMX, rewrites texture pixels, edits an existing editor window,
or learns arbitrary textures from a screenshot. All processing stays local.
The plugin source is part of pmx_appearance_reference.py, compiled on demand.

The comparison measures RGB statistics of corresponding visible materials;
it is a colour-balance approximation, not a claim of exact pixel equivalence.
Poses, camera projection, physics, transparent layers, missing artwork, material
morphs and unsupported MME effects can still differ. Sliders are global per model,
so a fit that harms a measured material is rejected rather than forced.


### Arbitrary PMX material visibility

Automatic matching skips hidden or unmeasurable reference parts instead of rejecting
swap outfits. Every candidate also compares the composited full model; both that
comparison and each measurable sampled material must avoid regression. Models
without opaque material samples use the full frame, with renderer
RGB already blended onto clear black, compared directly to the black-backed native
reference. Alpha is not multiplied a second time.
Unsupported reference-shader materials are reported explicitly. This is a bounded
colour-statistics fit, not exact pixel matching or reconstruction of missing art.


Reference-slot recovery uses a cross-process Windows file lock plus a saved
source/binary SHA-256 ownership record. A verified stale binary is reclaimed only
when no PMX Editor process is running. Unknown, modified or unmarked files remain
untouched. A tiny lock file is retained to avoid locking different file objects
across concurrent Sakura instances. Native captures and recovery can be verified
separately from the mocked protocol tests; the alpha regression test reads real
WebGL render targets against transparent and opaque black backgrounds.
