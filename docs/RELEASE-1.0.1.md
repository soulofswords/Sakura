# Sakura 1.0.1 — updated Windows release and illustrated guides

The Windows installers were refreshed on 28 October 2026. If you downloaded the earlier 1.0.1 installers, download the updated copies for these additions. The version remains 1.0.1 as requested; SHA256SUMS.txt identifies the refreshed binaries.

Choose **Sakura Companion** for conversation, local/cloud AI, Agent workflows and optional tracking. Choose **Sakura VTuber** for standalone tracking, Chat Reader, voice conversion and streaming. Install in separate folders. Updating preserves imported characters, settings, voices and AI weights.

## Added in this refresh

- **Settings > Theme > About Sakura** shows installed edition/version and release history.
- **Graphics** in Theme exposes Low, Balanced and High rendering quality, synchronized with the toolbar and saved automatically.
- **PMX backgrounds and props** share the character's 3D scene. In VTuber open Background; in Companion open Memory & privacy > Background & stage items. Tick the enable checkbox, import a complete PMX folder with textures, add the asset and arrange up to four static objects with position, scale and rotation. Unticking unloads scenery while retaining the character. Scenery uses the same 3D camera/depth/output capture and is intended for PMX/VRM characters, not the separate Live2D renderer.
- Separate **Companion and VTuber guides** include current UI screenshots and step-by-step instructions. Download the PDFs or offline HTML guide ZIP. Screenshots use demonstration data without personal models/accounts.

## Fixes included

- Library previews include the required PMX/VRM preview page.
- Telegram configuration waits for the previous polling loop to stop.
- Concurrent Agent web fetches retain public-address filtering.
- Expired phone pairings are rejected and no longer exhaust device slots. Listener restarts wait for the previous listener to finish.
- Agent review preserves approval-checkbox state through refresh, clears stale cards when action state changes elsewhere, and displays approval errors correctly.
- Command execution closes output pipes after success or timeout.
- Owner-only Jio setup recovers from expired sessions with Sign in again. **App users do not sign in to Jio:** cloud model downloads use their Sakura account. Owner publishing credentials are excluded from installers.

## Downloads and platform status

- Protected Windows x64 Companion and VTuber installers.
- Sakura Mobile **0.3.31** is the same APK as before. These Windows changes do not rebuild Android; desktop PMX scenery controls are not a phone-local scene editor.
- Separate illustrated PDF guides and an offline HTML guide bundle.
- **No refreshed macOS installer is attached.** A protected native Mac build needs a Mac host, unavailable in this Windows environment. Existing experimental source/bootstrap Mac support is documented in the repository and is not presented as a verified installer.

## Accounts, optional services and privacy

Cloud imports prompt for Sakura sign-in when selected. Google/LinkedIn/MCP and messaging services need user consent and supported integration setup. AI weights, optional hardware, keys and browser/sandbox dependencies are separate downloads/configuration. Skills guide a model but do not increase its parameters or configure missing services.

No personal character models, RVC weights, AI weights, owner/user sessions, MCP connections, API keys or conversation history are bundled. Windows executables remain unsigned. Code protection deters casual inspection but does not guarantee resistance to reverse engineering. Camera, phone and GPU behaviour depends on hardware; automated tests do not guarantee a fixed tracking frame rate.
