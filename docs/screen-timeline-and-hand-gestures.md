Screen viewing now creates a silent observation about every 20 seconds when chat,
recording, speech and screen reactions are idle. Each observation sees up to three
sampled frames from the preceding 22 seconds and available recent audio transcript.
The selected vision provider handles these requests; Local mode keeps images local.
Cloud mode therefore makes additional vision requests while Screen is enabled.

At most 30 short notes remain in RAM for ten minutes. They are available to normal
chat even after Screen is stopped, so the user can ask what happened earlier.
They are sparse observations, not a complete video recording. Missed scenes and
events before Screen was enabled cannot be reconstructed. Clear memory removes
the notes and invalidates an in-flight observation. Restart also clears them.
Normal chat answers, including answers about a video, follow normal chat persistence.
Background notes do not speak or trigger avatar animation. No camera collection
is added. Screen off stops collecting new images; VTuber tracking does not observe.

In AI Companion mode, explicit show/raise/lift-hand commands play a brief 3D pose.
An unspecified side means both hands; left/right refers to the character's own
side. Commands require a rigged PMX/VRM avatar and are disabled during tracking.
The pose holds briefly, opens available finger bones and fades back to normal.
Live2D requires model-authored arm parameters/motions and is not claimed supported.
