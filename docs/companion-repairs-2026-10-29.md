# Companion texture, voice and game repairs — 29 October 2026

Qoder's TGA replacement decoder and file-picker changes were present in source.
Browser verification found two additional replacement problems: the WebP RIFF
signature was wrong, and replacing a compressed DDS map retained its compressed
GPU format. Both are corrected. Replacement images preserve UV transforms and
colour space; oversized TGA headers are rejected before allocation.

## Original hair artwork

Luka-Revealing Dress's `hair_rukaAp_L65.png`, `ruka_hair_backlL65.png` and
`face_MikuAp_L65a.png` actually contain DDS bytes. Chromium's PNG decoder rejected
them. PMX texture loading now dispatches PNG, JPEG, BMP, TGA, DDS and sphere-map
filenames through the existing signature-aware loader. This is global, with no
source texture edits, recolouring, or deletion of saved user overrides.

A real browser render of that model loaded all five affected hair material maps
at 1024×1024, displayed pink hair, and reported no page errors.
The snapshot check retries unloaded textures and still saves only confirmed
path repairs. Missing artwork and ambiguous paths remain reported for selection;
snapshots cannot reconstruct missing original artwork.

## Teacher and microphone state

Each direct chat turn refreshes the language model's Friend/Teacher state from
saved settings. Mode reminders report the actual state. Teacher appearance repair
requests invoke the real texture-check UI and return its diagnostic result,
instead of generating fictional menu instructions or claiming a recolour.

Explicit Listen requests keep ownership of the browser microphone across screen
refreshes and temporary reply pauses. They no longer get diverted into the native
wake-only listener when a wake phrase is configured. Explicit mute clears that
request. Automatic listening still requires opt-in; multiplayer audio still
requires the wake phrase to address Sakura. Quiet-microphone VAD has a lower
noise-adaptive floor; silence, click noise and reply isolation remain tested.
Actual headset pickup and speech recognition require a physical-device test.

## Games and web answers

Single-player uses normal conversational listening. Multiplayer watches readable
HUD/scoreboard changes, with bounded progress comments and existing round-result
reactions. The watched player's score must be readable; another player's kill
feed is not evidence of their kill count. Progress comments are limited to once
per 30 seconds, and multiplayer observation polls no faster than ten seconds.

A supplied screen no longer disables text-only web grounding. Walkthrough queries
can include the detected foreground game's executable name; that name remains
untrusted context and is not proof of the exact game title. Screenshots are not
submitted as web-search queries. Existing private/sensitive-query guards and
search-provider configuration remain in force. Real games can require the user
to clarify the game, quest or objective.

## Mobile logo

The supplied Sakura Mobile image is used in the phone header and launcher icon
build input. This source change requires a new APK to appear on an installed
phone. No APK or public release assets were rebuilt as part of these repairs.
