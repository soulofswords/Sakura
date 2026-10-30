# PMX renderer verification — 29 October 2026

REA 6.8.0 inspected the local PMX Editor assemblies using its static managed
provider. No target assembly was loaded or executed. The inspected
`tools/pmx-editor/Lib/System/PmxEditorLib.dll` has SHA-256
`aa32252a1ef1d63f267e8243cfba7d6b849f9a7950e5414c75fdc0100f950404`.

REA identified the embedded resources. Supplementary resource extraction and
Windows D3DDisassemble inspected the compiled `basic` and `PmxEffect` effects.
In the latter's non-self-shadow pixel branch, `dp3` followed by `mad` with
0.5 constants forms the half-Lambert lookup. `ToonSampler` retains RGB and the
shader multiplies those channels into the surface colour. This evidence does
not support replacing half-Lambert with raw NdotL for this editor version.
The effect has other shadow/toon modes; these observations are not a claim
that every PMX Editor mode has an identical formula.

Sakura's existing reference override collapsed a coloured toon sample to its
red channel. It now uses RGB, preserving the existing ramp coordinate,
white defaults, material alpha and authored parameters. A real WebGL test
reproduced `[64,128,192] -> [64,64,64]` before the fix and verifies the original
RGB after it. White and absent ramps and ambient addition are also tested.
The shared ModelViewer path applies in Companion and standalone VTuber.

Seven Gratia `tex/` PNGs were entirely zero-filled despite retaining their
expected lengths. Same-name originals in
`Gratia/Default/Role/Textures/` decoded successfully. Only the seven zero-filled
destinations were replaced, atomically, with those same-model originals after
checking equal file sizes. SHA-256 verification confirms both desktop libraries
see the restored bytes. Original zero-filled data and a recovery manifest are
retained in the private temporary verification directory. No other artwork or
model files were rewritten. The corruption's time and originating operation
have not been established; shared/hard-linked copies alone do not prove cause.

The Gratia browser check now tests real restored textures and separately
injects broken HTTP image data to keep exercising neutral fallback/reporting.
A white fallback prevents black surfaces; it cannot reconstruct missing art.

This is a focused, evidence-backed compatibility improvement. It does not
establish pixel identity for every editor setting, sphere/shadow mode, material
morph, custom MME effect, malformed model or explicit saved user override.
Native editor binaries and extracted shader code are not shipped with this note.

## Stockings and blue tint follow-up

The earlier diffuse-plus-toon approximation omitted the editor's normal-lighting
vertex term. The recovered `PmxEffect` shader uses
`(ambient + 0.5 * NdotL * LightColor) * diffuse * AmbientColor * 2`
before the toon multiplication. REA-identified CIL plus supplementary CIL decoding
of D3DManager's defaults confirms DarkGray (169/255) for both default colours.
The reference shader now uses that normal-lighting law with Sakura's selected
light direction. This is a default-profile approximation; custom editor lighting
and effect modes can still differ. Pixel tests were updated to this equation,
and Traditional Miku #2 is tested specifically for dark zero-ambient stockings.
Its original white source atlas is unchanged. On a controlled render, stocking
mean RGB brightness changed from about 251 to 73 with specular/shine retained.

Two saved Miku #2 toon overrides mapped missing `toon.bmp` to `t/toon.png`, whose
pixels are blue. Those exact two overrides were backed up and removed. This
retains all other model mappings. PMX shading requests and the diagnostic now
disable automatic extension substitution: a missing BMP toon cannot silently
become an unrelated same-stem PNG. Exact-name copies and explicit mappings
remain supported. This prevents the check from reintroducing that blue cast.

## Presentation correction: flat anime style

The normal-lighting equation above was experimentally applied, but the user's
comparison rejected its rounded face/body shading. It is no longer the active
presentation law. The shared PMX shader now uses flat authored ambient fill
(`clamp(ambient * 2, 0, 1) * diffuse * toon`) and bounded sharp specular instead
of continuous NdotL diffuse shadows. Authored sphere maps still apply. This is
an explicit anime presentation choice, not a claim to reproduce every native
PMX Editor shader mode. A pixel test proves sideways light does not darken a
white flat surface, while zero-ambient cloth remains dark.

Both Traditional Miku variants were rendered for review: Miku.pmx's pale cyan
dress and Miku #2.pmx's dark stockings. Five additional auto-generated blue-toon
overrides on Miku.pmx were backed up and removed, without removing its diffuse
path repairs. Source texture bytes and explicit user colour/alpha edits remain
unchanged.


## Flat-fill saturation order correction

The screenshot comparison exposed early saturation of ambient before diffuse.
The shared flat presentation now uses
`clamp(ambient * 2 * diffuse, 0, 1) * toon`; previously it used
`clamp(ambient * 2, 0, 1) * diffuse * toon`.
A material authored at ambient .6 and diffuse .8 was reduced to .8 instead of
.96, dulling fabric independently of texture quality. A controlled WebGL pixel
now measures 245 instead of 204 for that material. Traditional Miku's isolated
fabric mean RGB changed from [145.8,185.8,192.1] to [172.8,220.4,229.5].
This correction applies to every PMX using the shared shader. It does not
rewrite PMX data, artwork, saved colour overrides, opacity or sphere textures.
Luka, Gratia and Miku #2 dark-stocking regression checks pass.

This remains the flat presentation requested after rejecting continuous normal
lighting. The retained REA disassembly establishes the editor has multiple
lighting branches. This isolated correction does not prove pixel-identical
rendering against every PMX Editor mode or custom lighting configuration.


## Explicit part-colour overrides

ModelMaterials previously updated material.color and a generated atlas, while
PMX reference lighting continued reading immutable authored diffuse/ambient
uniforms. Richie's e眼白 uses diffuse .8 and ambient .4, so a newly white atlas
was still attenuated to .64. Explicit colour strength now interpolates these
uniforms to neutral fill and tint; untextured parts interpolate diffuse to the
selected colour directly. Reset/detach restore captured uniform values.
Opacity-only edits leave authored values intact, and other materials sharing
the same atlas are not changed. No PMX or original image bytes are rewritten.
`tests/pmx-part-colour.cjs` uses the real Richie material in WebGL: isolated
mean brightness 154.895 -> 255 -> 154.895 after reset, shared iris map unchanged.


## Ice Miku: flat key fill and sphere/toon order

Ice Miku's authored diffuse and ambient colours include blue and purple.
The ambient-only flat presentation exaggerated these shadow colours and left
additive sphere-map colour outside toon attenuation. Retained PmxEffect pixel
bytecode combines base and sphere before applying ToonSampler. The shared shader
now follows that order. A controlled sphere+toon test verifies [48,64,80]
instead of the previous [64,96,128] for the same input bytes.

The flat mode now supplies a neutral key-fill term (0.25 before the material
factor of two), scaled with Ambient fill. Directional shading blends this
constant key toward NdotL. This constant is a presentation approximation,
not a recovered PMX Editor default. Completely zero-ambient materials retain
flat darkness for the existing stocking contract; this is also an explicit
compatibility choice, not universal PMX semantics. No model names are used.
On Ice Miku sleeve material 35, isolated mean RGB changes from
[200.87,200.87,255] to [243.60,243.60,255]; the authored files are unchanged.

A proposed sphere UV inversion was tested then removed: shader variants have
different coordinate conventions and evidence did not establish a safe global
UV change. Existing sphere UVs remain intact. Remaining faint lavender may be
present in authored material/ramp/sphere colours. Exact editor pixel parity is
not established. Both snapshot buttons remain diagnostics/comparison tools,
not automatic screen-colour estimators.


## Native reference bridge and rectangular toon regression

Supplementary reflection-only inspection of the installed PEPlugin, SlimDX and
editor assemblies identified the PmxView connector, PmxDraw.Manager render target,
PartsSelect visibility controls and view-lighting API. The owned startup plugin
was compiled with .NET Framework and run against Ice Miku. It returned distinct
native captures for material indices 16, 50, 0, 21, 27 and 47. Initial prototypes
that disposed the editor-owned render-target wrapper or fitted the whole image
were rejected. The final bridge keeps that wrapper alive, uses UI-supported
material visibility and normal editor rendering, and excludes floor shadows.
Temporary plugin files were removed and owned test processes stopped.

MMDLoader's square-canvas rotation was independently reproduced on 16×250 and
250×16 ramps. Swapping output dimensions preserves all pixels. Ran Yakumo's
Hair Tails and Hat2 now load 250×16 ramps with valid RGB instead of cropped
transparent black rows. The real-WebGL regression checks isolated hair mean
brightness above 180 and hat above 230 without changing artwork.

The appearance button and the texture-check callback share the same bounded
matcher. Separate corresponding-material mean/quantile measurements prevent
whole-image pose proportions from being treated as colour evidence. Candidate
settings that worsen a measured material are rejected. Undo and captured before
settings remain available. This does not reconstruct hidden artwork or guarantee
matching arbitrary PMX Editor effects; the UI states the remaining limits.
