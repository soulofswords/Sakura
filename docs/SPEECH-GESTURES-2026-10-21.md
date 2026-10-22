# Expressive speech and 3D game laughter — 21 October 2026

Audio-driven mouth opening now uses a bounded nonlinear envelope, with a maximum of 0.92 before user gain. Quiet clips are calibrated independently. Silence, cancellation and model switches close the mouth. Uses one available vowel morph at a time rather than guessing phonemes from volume. PMX/VRM custom mappings and mouth gain remain supported. Live2D receives open/form parameters, including the final audio-mouth override.

Speaking gestures alternate seven hand-emphasis patterns with quicker, smooth beats, larger elbow/arm movement and softened fingers. Face-tracking modes keep their tracking controls.

Game watch classifies explicit missed shots, repeated misses and player death. Miss classifications require multiple recent frames. Initial screen checks, repeated visible events, recent conversation and a 90-second game-event cooldown suppress unwanted repeated laughter. This uses periodic visual analysis, not game telemetry; missed shots cannot be detected reliably in every case.

PMX/VRM use a short laugh or a bent-forward laugh with position-based hands toward the abdomen. Bend direction follows the loaded rig's forward orientation. Motion begins on actual audio playback and returns to neutral. Live2D and tracking modes are excluded from these game laughs. Human laugh clips are independent of the selected TTS voice; source and license are in static/audio/reactions/LICENSE.md.

Validation: unit checks for mouth envelope, playback races, silence, poses, cancellation, format exclusions and game-event protocol/cooldown. Headless Edge loaded real Ringo PMX, a VRM and MIU2022 Live2D; played the WAV, observed mouth peaks around 0.85, confirmed cleanup, and checked finite 3D poses. No microphone, camera or live game was used. Screenshots exposed a reversed VRM bend, which was corrected. Local app refresh is performed separately; existing processes need restarting to load the updated Python and JavaScript.
