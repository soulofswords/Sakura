# Audit fixes — 26 October 2026

- Phone TLS refuses absent/mismatched SHA-256 pins. First pairing verifies the
  fingerprint displayed on the PC; remembered pairings retain their saved pins.
- PC API mutations require the exact bound origin, with an internal per-process
  capability for the authenticated phone relay. Foreign localhost ports receive
  no CORS grant. Native processes are not considered trusted merely by omission
  of browser headers.
- Model and RVC filenames render as text, never interpolated HTML.
- Password reset completion consumes a valid, expiring reset ID, never an email
  address as authorization.
- Rig detection is cached at bind time. Ribbon integration retains velocity.
  Diagnostic viewer imports match the application revision.
- Memory route guard spelling, tracking-only clear/refresh results and game-mode
  route registration are corrected. History sources use plain readable URLs.
- Cloud search reaches all games; empty root galleries show an empty state.
- Only authenticated phone requests update contact status; discovery throttling
  is per sender with a global bound, and allowed LAN addresses use explicit
  private ranges. Failed pair requests create no tokens. Forgetting one phone
  preserves other phone credentials.
- PC-changing chat commands require a single-use review decision. Calendar
  confirmation contexts are separated between desktop, phone and AI VTuber.
  Broadcast uses the configured loopback 18100/gateway endpoint, not fuzzy names.
  Scheduled web.fetch is no longer approved as a read-only tool.

Validation: 901 backend tests passed; cloud browser, phone discovery, private
Jio streaming and physics checks passed. Signed testing Android APK rebuilt and
verified. This is a targeted audit, not a guarantee that no vulnerabilities remain.

Second Jio account is additive. Its verified folder is PMX; separate encrypted
credentials, namespaced model IDs, routing and combined browsing preserve the
first account. Required original names are stored in verified repair archives
when Jio deduplicates filenames or rejects empty files.
