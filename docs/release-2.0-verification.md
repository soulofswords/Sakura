# Sakura VTuber and Mobile 2.0

This release publishes the standalone Windows VTuber installer and Android Mobile APK only. It does not update or publish a Companion installer. Shared application source remains in the private repository; no public source export or GPL conversion is claimed by this release.

Included VTuber/Mobile work: PMX transparent-fragment depth correction, smoother retargeting and cursor/model controls, restricted-CSP Live2D loading, resilient Live2D expression discovery, phone controls and connection updates, and simultaneous YouTube/Twitch chat-reader support. Hardware tracking, RVC and chat services require the relevant device, model or account.

Release fixes: malformed optional Live2D JSON no longer crashes expression discovery; the loopback Host check now covers pages, model files and generated audio, not only API routes. VTuber product metadata and Windows installer registration show 2.0; Android uses versionName 2.0 and monotonically increased versionCode 41. Companion's default product version is unchanged.

No personal character models, RVC weights, saved conversations, owner Jio sessions, Google sessions or MCP connections should be packaged. The existing installer extraction/backend smoke checks enforce edition isolation and empty user-model defaults. Dependency audits report advisories for the checked package set, not a proof of absence of vulnerabilities.

Distribution limits: Windows is unsigned; Android retains the existing local testing signing identity. Automated Java/WebGL/browser checks are not a physical-phone or live-camera test. Public VTuber source separation remains separate work because the current runtime shares implementation with the private Companion product.
