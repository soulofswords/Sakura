# Optional Companion camera vision

Settings → Camera & Audio → Companion camera access provides an explicit checkbox, off on each launch. It uses the selected camera and does not record microphone audio. A separate checkbox enables occasional idle camera comments (checks once per minute, only with camera access enabled). Disabling camera access stops its stream and cancels its pending observation/audio. Entering VTuber or AI VTuber mode stops it. Changing the selected camera stops it; re-enable to use the new device.

When camera access is enabled, ordinary direct messages include one downscaled JPEG. Screen/avatar inputs remain separately labelled. Gemini receives the image at Google's API; local Qwen-VL uses the configured local vision model. Ordinary text-only Qwen models cannot interpret camera images. Camera vision is separate from the tracking preview: its face-hiding control does not mask AI images. The UI explicitly discloses this.

Idle observations prefer silence, avoid repeated comments, and wait at least a minute after a direct reply and ten seconds after microphone activity. The observation request does not hold the conversation lock, so it cannot block a newly typed message. Results arriving after a direct message or camera shutdown are discarded. Images and idle camera observations are not stored in conversation memory. Normal direct answers are stored as text like other conversation turns.

Instructions ask the model to use visible gestures, objects and surroundings only, without identifying people, inferring private traits/feelings or inventing motion from a still image. This is occasional still-image context, not continuous video understanding.

Object-showing behavior uses the same prompts for Gemini and local Qwen-VL: recognize visible categories such as phones, headphones or controllers, acknowledge a visible detail, and respond with curiosity or delight without guessing brands or exact models. Idle observations return spoken text and a validated expression mood; the avatar applies that mood only when Reactions are enabled and the imported model has a suitable expression. Plain greetings do not force surprise, and no object or repeated observations should usually produce silence. Camera-off behavior is unchanged.

Tests cover camera permission races, selected devices, no microphone capture, stream cleanup, image validation, tracking isolation, image labels, memory exclusion, and idle-comment suppression. Live camera interpretation quality still depends on the camera view and chosen vision model.
