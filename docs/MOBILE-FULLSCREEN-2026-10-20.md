# Sakura Mobile 0.3.6 — full-screen model and microphone

- After a saved/transferred PMX, VRM or Live2D model finishes loading, it fills the phone display. Android system bars hide; swipe at an edge to reveal them.
- Added a large red microphone button with visible Mic off/on text and a crossed microphone when muted. Off by default; no automatic/background recording.
- Tap to start a speech turn, tap again to cancel. Recognized speech sends one message automatically; microphone turns off while awaiting/playing the assistant response. Late results after mute are ignored.
- Added native Android speech recognition with runtime microphone permission, service-availability/permission errors and recognizer cancellation/destruction.
- Call entry, switching mode, leaving full screen or backgrounding cancels microphone input. A permission dialog can finish without losing the first microphone request.
- Chat and settings remain accessible in an overlay; Back exits to the regular layout, and Full-screen model returns to the stage.
- Existing Local/PC choices, provider/model checks, location, chat, model transfer, voices and pinch/pan controls remain available. App name/package/signing key unchanged; install over the old Sakura Mobile to preserve saved phone models/settings.

Validation: Java compilation, R8, APK signature verification and archive/model-exclusion checks passed. Browser checks verify full-viewport sizing, red-mic default/on/off/cancel/send/background gating, PMX/VRM/Live2D rendering, real Live2D two-finger pinch, settings and transfer workflow. Physical-device microphone permission, recognition service and Android system-bar behaviour still need phone testing.

SHA256: 614da5213c08a2dcb9c61c8a64b977a4674d4a4ffc8299ed10a83f22ef9dca80
