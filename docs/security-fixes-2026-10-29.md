# Security and packaging corrections — 29 October 2026

Implemented after independently checking the installer review:

- Agent action approval now opens a native Windows confirmation with the stored
  proposal, arguments and command-permission choice. The runtime rechecks the
  action digest under its execution lock; rejecting or changing the proposal
  cannot execute it. Configuration imports and enabling automatic workflows
  also require native confirmation. The loopback page bearer alone is insufficient.
- This protects the normal consent boundary, not against malware controlling
  the same user's desktop. Other operating systems fail closed until a native
  confirmation implementation is provided.
- Phone private keys receive protected Windows DACLs before writing new key
  bytes and on reuse. Existing certificates/pins remain unchanged. Legacy private
  settings, logs, audio and browser-profile permissions are restricted in place;
  model/voice libraries are not moved or recursively modified. The default
  installer remains per-user LocalAppData; no wholesale storage migration occurs.
- Removed developer-drive SDK auto-discovery. A custom SDK remains available via
  the saved user selection or ARSDK_ROOT. This is not a claim that every optional
  third-party DLL has undergone publisher-signature validation.
- Camera registration checks compare the actual owning installation. Removing
  another edition's camera is refused. The uninstaller removes only its owned
  registration and matching Windows startup entry.
- Startup fallback uses desktop.py, the bootstrap retained by protected builds.
  Exhausted backend ports receive an actionable desktop error.
- Browser microphone and voice memo decoding can use bundled PyAV without an
  external ffmpeg command. WAV and real generated WebM decoding were tested.
- Protected distributions include a minimal RVC worker bootstrap; incompatible
  optional interpreter ABIs receive an explicit error. Optional Windows RVC setup
  supports CUDA, DirectML and CPU with pinned base-model SHA256 checks. Runtime
  downloads remain opt-in. A fresh protected clean-machine RVC conversion is
  still required before describing the complete release path as verified.
- Protected installer creation runs payload inspection before returning success,
  including required packaged modules/worker/setup checks. Native compiler
  temporary source copies are removed after compilation.
- Android build supports private release signing via environment variables and
  restricts the existing keystore's ACL. Default testing builds are clearly
  labelled. No existing signing identity is silently replaced; production key
  custody/backup and compatible rotation remain release-owner decisions.
- Standalone VTuber taskbar description now uses its correct product name.
- Jio transfer diagnostics identify the failed service host and network phase
  while excluding credentials, signed URLs and query strings. Existing verified
  checkpoints remain reusable. The transient stage upload recovered and all
  14 stage PMX entries published; authenticated temporary-install verification passed.

Additional requested UI integration:

- Companion has a dedicated Background & stage items toolbar button.
- Both model panels include MikuMikuDance beside PMX Editor. The executable is a
  user-selected local preference, not a developer path baked into distributions.
  The button validates the PMX currently displayed in Sakura, starts a new MMD
  process, waits for that process's file-drop window, and sends its existing PMX
  path via WM_DROPFILES. It does not modify the model or overwrite another MMD
  scene. MMD may show the model's own confirmation dialog. A queued import is
  reported as a request, not independent proof of a successfully rendered model.

Validation: full Python suite 1,206 passed / 171 subtests; subsequent targeted
checks 64 passed / 6 subtests after final follow-ups. Native uninstall checks and
Companion/VTuber layout, handover and cloud-scenery browser checks passed.

Source and local development products were refreshed. No new protected installer
or APK was built or published during this correction task.
