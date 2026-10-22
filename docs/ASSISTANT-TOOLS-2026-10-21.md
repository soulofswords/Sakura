# Practical assistant tools — 21 October 2026

## New implementation

- Fixed tool registry and capability discovery, shared by local/cloud chat command routing. PC utilities avoid unnecessary vision capture and language-model generation.
- Windows CPU/RAM/system-drive/battery/uptime measurements. CPU starts with a sampling state rather than an invented percentage. No new Python dependencies.
- Default Windows multimedia output volume read/set/up/down/mute/unmute via Core Audio, with read-back verification. No shell or generated scripts.
- Read-only file-name search in the top level of standard Downloads/Documents/Desktop paths, at most 5000 entries scanned and 20 matches. This is not a recursive file manager; redirected/OneDrive folders may need future known-folder resolution.
- Explicit sequences of up to five supported actions, preflight of action vocabulary and permissions, sequential execution, structured per-step results, stop after failure, cancellation before the next step, and a session-only history of the latest 20 sequences. App launching confirms OS acceptance, not successful completion of the app's startup. Previously completed steps are not rolled back.
- Settings → General → PC tools: live status while the panel is visible, volume controls, available actions, recent results and Stop current sequence.
- Separate off-by-default paired-phone permissions for status/volume and clipboard text. Paired phone requests are forwarded to the local permission-enforcing API; no arbitrary shell/file paths are exposed on the phone route.
- Sakura Mobile PC tools tab: status refresh, set PC volume, explicitly read PC clipboard into a text box or send that box to PC clipboard. No background clipboard polling or automatic overwriting of the phone clipboard. Plain Unicode text limited to 4096 characters.

Examples: `PC status`, `set volume to 30%`, `find file report in downloads`, `open calculator then set volume to 30%`, `show capabilities`, `show task results`, `cancel current task`.

## Boundaries

This implements bounded tools, not a universal goal solver or arbitrary autonomous planning. It does not add self-modifying code, model retraining, unattended experimentation, a full world model, internet remote control, notification relay, or persistent/shared chat memory. The previous session-only chat preference remains. Existing saved app preferences, local/cloud speech/chat, vision, phone pairing/reconnect, model transfer and reminder capabilities remain.

The current phone link uses authenticated HTTP on trusted home Wi-Fi, not encrypted transport. The new clipboard setting says this explicitly. Automatic clipboard synchronization is intentionally not claimed. Native Android background clipboard access remains OS-restricted. Real phone permissions, physical LAN and native call behavior need device testing.

No Windows installers or public GitHub assets were rebuilt for this implementation. Local PC applications refreshed. A local Sakura Mobile 0.3.18 APK includes the new controls; version code 24, same package/signing identity. Phone tools need the updated PC app too.

Validation: assistant tool/permission/workflow/cancellation/file-boundary tests and existing command/reminder/mobile-link/clipboard tests; headless PC tools dashboard and phone source/packaged WebView checks. Windows status and volume read were checked without changing system volume. Clipboard contents were mocked, not inspected. Compilation/signature/archive verification recorded in audit-results. No private chat, API key, model or clipboard content was added to release files.
