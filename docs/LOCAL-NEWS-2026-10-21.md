# Local news update — 2026-10-21

PC Companion and Sakura Mobile now use the India English news edition. News area is an optional saved city/state (for example Mumbai, Maharashtra). General news and local-news requests use that area; explicitly named places/topics override it. Blank means national India headlines for general requests; local news asks for a city/state instead of guessing. This is a saved preference, not automatic GPS travel detection. PC-connected phone mode uses the PC preference; standalone phone mode uses its own setting.

Validation: 40 PC Python tests passed, actual Android Java query cases passed, mobile location/command regression checks passed, PC utility JS checks passed. A live Maharashtra RSS fetch returned recent dated publisher-labelled headlines in 1.02 seconds. Source WebView checks passed. Android 0.3.14 compiled, obfuscated and signed; APK archive integrity, UI UTF-8, and model exclusion independently checked. A transient build-script encoding issue caused a false final assertion; corrected the script and re-ran equivalent package verification.

Local Companion files refreshed. Windows installers and GitHub were not updated. Install the new Sakura Mobile APK over the existing version. Physical phone behavior still requires testing.
