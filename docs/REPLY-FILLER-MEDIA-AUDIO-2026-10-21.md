# Repetitive replies and media speech — 21 October 2026

Timer and alarm confirmations no longer include their internal identifiers. Timers still retain IDs internally and cancellation by identifier remains supported. Spoken listings use labels and remaining time.

Chat quality checks now detect long near-identical answers across recent turns, as well as combinations of empty promises of help and evasive follow-ups. One bounded regeneration uses the current question and excludes those bad assistant examples. Short acknowledgments, explicitly requested repetition and deterministic common Hindi/identity answers remain allowed. This is a heuristic, not a guarantee against every model quality error.

Speech instructions explain `btw`, discourage stock question-praise and specify that avatar cup size cannot be inferred from an image; actual measurements and a sizing system are needed.

When automatic browser microphone listening and computer audio context are both enabled, each command requires the configured wake phrase (default `hey sakura`). A prior armed follow-up cannot let narrator speech through. The explicit microphone button keeps its existing behavior. Video/computer audio remains observed context for the screen reaction pipeline and is explicitly marked as not a user request. Native offline wake listening already requires its phrase. This does not perform speaker identification: media containing the wake phrase can still trigger recognition. The guard is active when screen/game computer audio context is enabled, not a detector for all playback anywhere on the PC.

Validation: 38 Python tests for reminders, chat quality/context, Hindi and screen audio passed; browser-module tests for media microphone commands, screen audio and continuous microphone passed. Live Qwen generation was attempted but the local runtime at port 11435 was unavailable; the report records connection failures and must not be treated as successful model conversation validation. No new microphone recording or camera access was performed. Local PC products refreshed; restart required. No installer, APK or GitHub changes in this task.
