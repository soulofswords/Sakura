# PMX colour and model-browser location — 29 October 2026

The prior texture-decoder fix restored the correct artwork, but did not make
Sakura's lighting match PMX Editor. Traditional Luka exposed the remaining
difference clearly: its pink kimono and white borders rendered grey/mauve.

The existing generic material pass replaced authored ambient colours with a
small constant and reduced additive sphere-map contributions to 12%. In addition,
modern Phong lighting did not reproduce MMD's legacy diffuse-plus-ambient sum.

PMX materials now retain their original diffuse and ambient values in metadata.
A separate reference lighting shader combines those values with the authored
toon ramp, clamps the legacy lighting factor before applying the texture, and
converts the factor to the renderer's linear colour space. Additive sphere maps
use their authored contribution. Runtime diffuse changes remain multiplicative;
alpha, UVs, source files, texture replacements and saved part edits are retained.
VRM and Live2D shaders are unaffected.

This is an MMD-style approximation, not a claim of pixel-identical PMX Editor
output. Camera, editor light settings, missing artwork and explicit user edits
can still produce differences. Missing optional toon/sphere images use the app's
existing neutral fallbacks; they are not substituted with another model's art.

Validation includes a real WebGL render of Traditional Luka: pink dress pixels
and white trim are present, authored material values and alpha are retained, and
no shader compilation errors occur. Luka-Revealing Dress and Miku-Elegant
Princess also load and render with no shader compilation errors. The test route
supplies neutral missing-image fallbacks matching the production asset resolver.

Local model selection now remembers its folder separately for PMX, VRM and
Live2D. Selecting a search result remembers the result's actual parent folder.
The location survives page/app restarts; a removed folder falls back to its
nearest surviving parent. Cloud import also remembers its last folder separately
for format and character/stage/prop library. No model files are moved.

Restart an already-open desktop app to load the new renderer and browser code.
No Unity migration, installer build, APK build or public release update is part
of this change.
