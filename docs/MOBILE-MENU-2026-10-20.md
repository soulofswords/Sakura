# Sakura Mobile 0.3.7 — menu and address preference

- Replaced the Chat & settings text button with a labelled hamburger menu that opens/closes the existing panel.
- The header, menu panel, status and microphone now occupy separate grid rows. Larger phone text and landscape layouts no longer place panel content beneath the header or microphone.
- Sir/Ma’am/No title saves immediately when selected, without needing Save settings or changing API configuration. It remains selected on reopening. Pending old speech is stopped, and both cloud providers receive the current preference with an instruction to ignore outdated titles in conversation history.
- One mobile product going forward: Sakura Mobile includes Local assistant, PC connection, VTuber expression controls and phone-camera tracking. The build command defaults to this APK; legacy --edition vtuber arguments now build the combined Sakura Mobile instead. Existing archived VTuber Mobile files were not deleted.

Validation: signed APK Java/R8/archive checks passed. Source and packaged/obfuscated browser checks passed for portrait, landscape and larger-text panel spacing, hamburger accessibility, immediate/persistent address selection, microphone controls, chat and PMX/VRM/Live2D rendering and transfer. Live cloud-generated wording and physical Android behaviour still require phone testing.

Install over Sakura Mobile; app/package/signing identity is unchanged. No character models are bundled.

SHA256: 472f2ea80e3e7f6d6d185fd95b9213d1705e5bcea58312930c1b7cc6f554040b
