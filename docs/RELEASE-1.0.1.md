# Sakura 1.0.1 — Windows fix release

Sakura 1.0.1 replaces the 1.0.0 Windows installers. It changes no features, no interface and no file
locations: it is the same product with the defects found by the post-release audit corrected. Install
over 1.0.0 or into a fresh folder; your characters, voices, settings and AI models are untouched.

Choose Sakura Companion for conversation, local/cloud AI, Agent workflows and optional VTuber tracking.
Choose Sakura VTuber for standalone tracking and streaming, without the companion language model.
Keep them in separate folders.

## What 1.0.1 fixes

- **Character thumbnails now render.** In 1.0.0 the installer left a preview page out of its own payload.
  The local character library renders every PMX and VRM thumbnail through that page, so with it missing the
  library silently kept showing each character's name as plain text, and hovering did nothing even though
  the panel promised "Hover a 3D preview to rotate it". Live2D thumbnails were unaffected because they come
  from the server. The page now ships, and the build fails if any page a shipped script loads is missing
  from the payload, so this cannot quietly come back.
- **Telegram reconfiguration no longer drops messages.** Saving a new bot token or new chat IDs while the
  previous poller was still shutting down could start a second loop, and the retiring loop had already
  acknowledged messages neither one answered. Reconfiguration now waits for the old loop to stop and, if
  it has not, refuses and tells you to retry a moment later instead of running two pollers.
- **Agent web fetches keep their address filter.** Two lookups finishing out of order could restore the
  system resolver while another fetch was still in flight, which let a public address be redirected back
  to this PC's own loopback. The filter is now reference-counted, so it stays until every fetch is done.
- **Expired phone pairings stop working.** A pairing you had let lapse could still prove a phone's
  identity to the PC. Expired pairings are now refused, and they are cleared out before they can fill the
  32-device list and block a new phone from pairing.
- **The phone link no longer stacks listeners.** Turning the link off and straight back on could leave
  the closing listener holding the port while a second one started. It now waits, and tells you to try
  again if the previous listener has not finished closing.
- **The Agent review panel stops interrupting you.** While an approval was pending, the 15-second refresh
  could re-draw the panel, wiping your tick in the "remember this" box and scrolling back to the top
  mid-read; an expired step left a dead Approve button on screen. The panel now only re-draws when the
  action actually changes, and an expired approval reports why instead of going quiet.

## What did not change

Sakura Mobile **0.3.31** is the same APK 1.0.0 shipped, byte for byte — the same SHA-256 as the published
1.0.0 asset. No file inside it was affected by the fixes above, so it is included in this release for
completeness rather than renumbered. If the phone's character preview was blank, that was the PC's missing
page, and updating Sakura on the PC fixes it.

## Verification

Every fix above has an automated test, including two regression tests written against the pre-fix code and
confirmed to fail before the change. The full Python suite, the installer clean-install checks, payload
integrity inspection and the release browser gate all run as part of producing these installers.

Two honest limits: the Agent review-panel changes are frontend behaviour that the automated suite does not
cover, so they were checked in the running app rather than by a browser test; and the Windows executables
are still unsigned, with the same SmartScreen prompt as before.

## Privacy and known limits

No personal character models, RVC weights, language-model weights, account sessions, MCP connections, API
keys or conversation history are bundled in either installer. Protected/obfuscated code is a deterrent, not
a guarantee against reverse engineering.

The messaging gateways (Telegram, Discord, Slack, WhatsApp) need your own credentials and, for WhatsApp's
webhook, a reverse proxy that rewrites the Host header, because Sakura deliberately accepts API calls only
when the address names this machine. That host check is DNS-rebinding protection and was not relaxed in
1.0.1.
