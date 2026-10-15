# Screen and Game audio

In AI modes, Screen viewing enables local speech recognition of the default Windows playback output. Game mode uses the same Screen capture session. Settings → Camera & Audio → Screen & Game audio lets users disable listening or select up to four playback, microphone or virtual cable inputs. Browser Screen sharing still captures audio on the PC backend, not browser tab audio.

Short segments are captured in memory, converted to 16 kHz mono and transcribed by the existing local Whisper model. Recent transcripts expire after 30 seconds and accompany only current screen questions/reactions. They are untrusted observations, never commands. Raw recordings and transcripts are not saved to conversation memory. Replies may reflect the audio. Gemini receives the transcript alongside the snapshot; local LLM keeps both local.

Listening pauses during AI requests and avatar speech, with a three-second playback tail guard. Turning Screen off stops capture and clears context. Loss of the frontend heartbeat stops the session. VTuber tracking-only mode cannot start this AI feature. No changes are made to device or other application volume.

Windows uses PyAudioWPatch WASAPI loopback. On macOS, choose an installed virtual loopback input such as an OS-configured audio routing device; automatic macOS playback capture is not implemented. Device switches may require Refresh audio sources. Transcription covers speech, not reliable music or sound-effect recognition. Recognition quality and speed depend on the recording and CPU.

Checks: mocked capture downmix/resampling, playback pause, source limits, stop/expiry, HTTP tracking-mode guard, ephemeral LLM context, real default-output capture, and synthetic speech through local Kokoro→Whisper. Native macOS hardware is unverified.

Capture API: [PyAudioWPatch documentation](https://github.com/s0d3s/PyAudioWPatch).

## Continuous capture and mode routing

Normal AI Screen mode starts the browser's selected microphone (with permission), using the existing silence/wake-word conversation pipeline. Computer playback is controlled separately by the audio checkbox. Turning Screen off stops a microphone that Screen started; a microphone already enabled independently is retained. Manual microphone disable is respected.

AI VTuber starts screen capture and YouTube chat, stops microphone conversation capture, and forces computer-only source selection on both client and backend. Chat replies receive the latest frames and current computer-audio transcript. Microphone conversation can resume after stopping AI VTuber if it was previously enabled.

Screen capture now runs continuously while enabled: native desktop capture refreshes at approximately 3 frames/second; browser sharing requests up to 30 fps. A short in-memory buffer supplies up to three recent chronological frames to each AI request. Nothing is saved to disk. Capture and buffers are cleared when sharing ends. AI vision is sampled analysis, not a video-rate streaming model; requests and spoken reactions retain rate limits to keep CPU/API use bounded. Audio capture continues while local speech recognition processes its previous segment, with bounded backlog and stale segments dropped.
