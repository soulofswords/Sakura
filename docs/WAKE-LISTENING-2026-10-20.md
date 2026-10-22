# Sakura optional wake listening — 20 October 2026

## Mobile 0.3.8
- Local settings → Wake phrase: download the optional 40 MB English offline pack, choose Hey Sakura or a custom phrase of 2–6 English words, then enable background listening. Wake detection/transcription is offline; recognized questions go to the saved cloud provider. Requires saved API configuration and a phone model.
- Say the phrase, wait for the short tone, then ask the question. The limited-vocabulary wake detector checks supported words and the command recognizer listens up to 14 seconds.
- User-started microphone foreground service with required microphone/notification permissions and persistent Stop listening notification. Red mic shows Wake on while listening and can stop the service. No background GPS or camera access.
- Listener pauses for manual mic, foreground chat/playback and communication/call audio modes. Background answers use the saved provider/voice; Android TTS is a fallback if provider speech fails. Background history is synchronized when reopening Local mode.
- Avatar rendering and WebView timers pause when the activity stops. Wake mode remains extra battery/CPU/RAM work: Vosk small models are not a hardware/DSP hotword solution. Real consumption has not been measured.
- Open and enable from Sakura first. No boot receiver, forced restarts, hidden notification or automatic microphone service resurrection. After force-stop, reboot, system/service stop or an unsupported phrase, reopen and enable again. App-opening, calls requiring confirmation and current-location requests need the visible app. Background English speech is supported in this build.

## Windows Companion local app
- Settings → AI Assistant: optional offline PC wake pack (~55 MB), existing wake phrase field and enable checkbox. Works independently of browser rendering/visibility using the default Windows microphone, including minimized/hidden Companion windows. Cloud/local AI reply routes are unchanged.
- Say the phrase, wait for a tone, then ask. No real microphone was accessed during development tests.
- While wake listening is running, X hides the Companion in the tray. Tray controls: Open Sakura, Stop wake listening, Quit Sakura. Quit ends the listener; an exited process cannot hear. The feature is disabled in tracking-only/AI VTuber microphone-excluded modes. Does not install a boot/startup service.
- Separate native microphone ownership and playback gating prevent the listener recording assistant speech or competing with manual input. Hidden native windows skip model rendering.
- Updated owner-local copies at F:\AI\assistant. Windows distribution EXE installers and GitHub releases were not rebuilt/published by this change.

## Validation and limits
PASS: Android Java compilation/R8, signature, archive/model-exclusion checks, pinned dependency integrity, arm64 Vosk/JNA 16 KB ELF segment alignment and APK native-library alignment.
PASS: actual Java wake phrase validation and native service/permission/notification contract checks.
PASS: source and packaged/obfuscated browser checks for opt-in/custom wake settings, red mic wake-state/stop, foreground wake routing, background-history restoration, full-screen menu sizing, saved address preference, PMX/VRM/Live2D rendering, pinch and transfer.
PASS: real offline speech model with generated Hey Sakura audio; unrelated synthetic speech rejected. Windows detector tested through actual decoder with fake sounddevice streams for wake + What time is it; no actual microphone.
PASS: desktop control/microphone ownership/playback resume/VTuber guards, assistant regression tests and existing lip-sync/continuous-mic/startup checks.
Physical Android permission, locked-screen audio, call handoff, OEM battery restrictions, tray UI and real custom-phrase recognition still require device/user testing. No zero-battery or universal accuracy claim.

APK: Sakura-Mobile-Android.apk
SHA256: dfafdf8855dafa529da11e48d89e534c0550d31abcfdc6f0e5a3ffc46e10dfea
