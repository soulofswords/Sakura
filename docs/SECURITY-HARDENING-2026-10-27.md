# Sakura security hardening — 27 October 2026

This pass addresses the confirmed findings in the owner's supplied Qoder report.
It is not a guarantee that the application is free of vulnerabilities.

## Account boundary

- Desktop settings and account routes accept only Sakura's official library URL.
  Substituted HTTPS hosts and localhost cannot receive passwords or saved sessions.
  Internal owner/test clients can explicitly opt into loopback; the product API
  never exposes that option.
- Failed sign-in no longer reveals pending reset IDs or whether a mailbox recovery
  session is waiting. Password reset is finished on the page opened by the email
  link. Existing reset expiry, one-time consumption and local request guards remain.

## Android boundary

- The renderer loads under a separate HTTPS origin, `models.sakura.invalid`.
  This is an app-intercepted virtual origin, not an external model server.
- The full Java bridge is replaced by a capability-gated gateway. Only the main
  controls document receives its random per-activity capability. Renderer frames
  cannot read the parent facade, and unauthorized gateway calls are rejected.
- Parent/renderer communication uses an explicit operation list and exact origin
  and source checks. Main controls cannot be embedded or navigated into a model frame.
- Content security policies, MIME protections, no-store on the privileged document,
  disabled cleartext traffic and restricted navigation provide additional boundaries.
- Native replies parse exactly one JSON object and quote it as data before JavaScript
  evaluation. Trailing code is rejected. Network requests run through asynchronous jobs.
- PC-controlled camera starts default to off. A visible phone switch grants access
  to the currently paired PC while Sakura is open. Revoking it stops tracking.
  Renderer camera requests require a lease initiated through trusted controls.
- TLS proof is local to each request. Failed pairing clears the live session.
  Wake downloads acquire their busy flag atomically; history size is checked before
  parsing. Single-task launch and configuration handling reduce duplicate/recreated
  activities. Camera/microphone still use Android's permissions.

## Desktop correctness and resource limits

- Multi-step commands retain their phone/desktop channel through execution and approval.
- Avatar capture is skipped without a recently authenticated connected phone.
- Appearance changes ignore stale startup reads and serialize saves.
- MCP discovery may retain a large catalogue, but planner input is relevance-ranked
  and bounded to 80 tools / 24,000 UTF-8 bytes. Tool descriptions remain untrusted;
  this does not grant permission to execute them.
- Local model status leaves the async API event loop; the provider label is corrected.
- Small-context trimming preserves fresh clock instructions before verbose style rules.

## Verification and delivery

- `tests/test_security_hardening.py` exercises rejected account destinations, reset
  isolation, phone-channel propagation, planner bounds and the actual compiled Java
  gateway and native-reply encoder.
- `tests/mobile-security-boundaries.cjs` verifies real browser cross-origin isolation,
  renderer load/tracking RPC, camera lease revocation and Java-generated injection tests.
- Other browser checks cover pairing, model transfer, appearance races, camera consent,
  expressions, MCP connections and Companion approvals.
- APK version 0.3.31 (37) is signed and packaged without character or LLM models.
  Install the rebuilt APK on the phone to receive native security changes.
- The deployment receipt records the selected desktop files, backups and destination
  hash checks. Restart each desktop edition to load its updated Python code.
- No blanket Git commit, release, installer build, database migration or credential
  rotation was performed. Physical-phone camera/tracking behavior still needs a
  device check; browser tests do not replace it.
