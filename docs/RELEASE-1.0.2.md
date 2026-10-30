# Sakura 1.0.2 — PMX colour and texture reporting, Agent metering

**Status: draft. The 1.0.2 installers are not built and nothing is published yet.** Delete this line when the installers and SHA256SUMS.txt are attached.

Choose **Sakura Companion** for conversation, local/cloud AI, Agent workflows and optional tracking. Choose **Sakura VTuber** for standalone tracking, Chat Reader, voice conversion and streaming. Install in separate folders. Updating preserves imported characters, settings, voices and AI weights.

## PMX rendering and texture reporting

- **Authored PMX colour is combined in the file's own numbers.** A PMX stores texture texels, ambient, diffuse and the toon ramp as raw 0-255 values and shows the result directly; Three decodes textures to linear, scales the light sum and re-encodes once, which is why uploaded models arrived grey, washed out or tinted. Sakura now recovers the raw texel and applies the authored ambient and diffuse before the output encode, so any PMX reads nearer its file's own colour. This is the arithmetic recorded in PMX Editor's disassembled shader branch (docs/pmx-rea-verification.md), **not** a pixel match of its viewport: Sakura uses a flat anime presentation by default. On Windows, automatic appearance matching now reads actual PMX Editor renders through an owned, temporary plugin; native captures were verified separately from the mocked protocol tests.
- **Model Settings > PMX appearance** adds eight per-model sliders - Brightness, Ambient fill, Authored material tint, Toon shading, Directional shading, Sphere/shine maps, Specular highlights, Colour saturation. They apply to every PMX through the same shared shader path, save per model, and **Reset appearance sliders** returns them. The defaults are the global behaviour; nothing is tuned for one named character.
- **Match appearance from PMX Editor** captures the editor reference and fits saved sliders only when measured colour difference improves without worsening the whole-frame or sampled-material checks. Hidden/occluded parts are skipped, translucent models can use the whole frame, and **Undo automatic appearance match** restores the previous settings. Texture checks also run this comparison after confirmed path repairs. This is colour-statistics fitting, not texture reconstruction or exact pixel parity.
- **Reference capture cleanup and packaging** use a cross-process lock and verified ownership records. Active editor jobs and unknown files remain untouched; generated reference plugins and job residue are excluded from installers. Both editions retain their existing user-writable Local AppData installation default. Custom read-only folders still cannot host the reference plugin.
- **A load-time texture check names the file that failed, per slot.** A PMX can point at a colour texture and a separate shine/toon texture in the same material; a missing colour file and a missing shine file are different problems. The report now lists them separately, states that the affected surfaces keep their authored colour, and stops blaming the diffuse file for a shine failure.
- **Unreadable artwork gets a neutral stand-in matched to its slot** - white for a multiply sphere, black for an additive one - instead of an unbound texture, which WebGL samples as zero silently and turns a whole model into a silhouette. Recoverable files are restored from their intact originals; genuinely missing ones are reported, not guessed or downloaded.
- **Zero-filled and corrupt textures are detected and repaired where the intact original exists**, and the model is checked after the repair in real WebGL rather than by trusting the file name.
- **Full-model before/after snapshots** capture the whole character from a fitted camera while your view stays where you put it, so a check cannot silently compare two different poses.
- The selected PMX can be sent straight to MikuMikuDance, and PMX appearance differences are compared in the native editor on request.

## Agent

- Every model call is metered, including delegated child runs and tool-execution calls, and usage budgets, loop guards and health gates are enforced against them.
- Task history is shared across processes, so a task started in one window remains readable after a restart; workspace tools were simplified with session approval policies and tool self-setup.
- Evidence indexing, reviewed skill imports and observability/evaluation gates ship with the release.

## Characters, cloud library and streaming

- Cloud folder hierarchy is preserved, verified transfers resume instead of restarting, retained entries are normalised when a source folder moves, and long folder labels wrap inside their cards.
- Stage and prop libraries are separate, and an additional VTuber instance starts fresh rather than inheriting a dead scene.
- Local approvals and private state were hardened, packaging repairs landed, and static PMX scenery shaders stay valid on models without morphs.

## Downloads and platform status

- Project website: <https://soulofswords.github.io/Sakura-website/> — features, setup and guides. The in-app Settings > Theme > About Sakura block links to it beside the release page.
- Protected Windows x64 Companion and VTuber installers, with SHA256SUMS.txt.
- Separate illustrated Companion and VTuber PDF guides (29 October 2026, Version 1.0.2) and the offline HTML guide bundle. Guide screenshots use demonstration data and show no personal character or account.
- **No refreshed macOS installer is attached.** A protected native Mac build needs a Mac host, unavailable in this Windows environment. Existing experimental source/bootstrap Mac support is documented in the repository and is not presented as a verified installer.
- **Sakura Mobile 0.3.32 (Android, versionCode 38)** is rebuilt because this release changes files the APK bundles (`static/js/**` and `static/vendor/**`, including the model viewer and PMX loader used for phone-local viewing). The Android sources, manifest and certificate pinning are unchanged in this release; the higher versionCode installs over an older build in place.

## Accounts, optional services and privacy

Cloud imports prompt for Sakura sign-in when selected. Google/LinkedIn/MCP and messaging services need user consent and supported integration setup. AI weights, optional hardware, keys and browser/sandbox dependencies are separate downloads or configuration. Skills guide a model but do not increase its parameters or configure missing services.

No personal character models, RVC weights, AI weights, owner/user sessions, Google or MCP connection files, API keys or conversation history are bundled. Windows executables remain unsigned. Code protection deters casual inspection but does not guarantee resistance to reverse engineering. Camera, phone and GPU behaviour depends on hardware; automated tests do not guarantee a fixed tracking frame rate, and PMX appearance sliders change how Sakura lights a model without promising it matches any other viewer.
