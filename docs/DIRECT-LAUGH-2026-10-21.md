# Direct laugh request — 21 October 2026

The original laugh path was connected to classified game events only. Saying or typing “laugh” reached ordinary LLM chat and did not return a motion or laugh audio.

Added a bounded direct-command parser before the LLM. Laugh/chuckle/giggle and supported Hindi/Hinglish requests return the short recorded laugh. Laugh harder/belly laugh/holding your stomach requests return the longer bent-forward laugh. Negative requests, quotations, medical mentions and general questions about laughter are excluded. The same endpoint handles local, cloud and AI VTuber requests.

The frontend uses the existing recorded-audio/3D-motion helper, starts motion on audio playback and bypasses TTS for this command. The selected TTS voice does not change these recorded clips. No game event, enabled screen viewing or automatic Reactions setting is needed. Live2D and active face tracking remain excluded from 3D poses, with a capability explanation rather than claiming to perform the action.

Validation: parser and endpoint regression checks; helper playback/cancellation checks; real PMX/VRM playback of short/deep WAV clips with mouth movement, concurrent motion and automatic neutral return; Live2D exclusion. No microphone, camera or external AI API used. Both local PC products refreshed; restart to load Python and frontend changes. No installer or GitHub release created.
