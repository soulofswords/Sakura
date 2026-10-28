# Faster desktop startup

Companion and standalone VTuber display the first complete character frame
without waiting for Windows voice enumeration or microphone/speaker discovery.
Those controls populate immediately after the startup cover is removed. The
saved voice is applied before the startup greeting is synthesized.

In Companion, private local-model runtime configuration no longer delays HTTP
and Qt window startup. Chat, model-settings changes, warmup and tracking-mode
transitions synchronize with that initialization so an old setup cannot race a
new selection or reload inference after entering tracking-only mode. Saved RVC
workers start after the renderer reports ready, avoiding competition during
character upload. Shutdown waits for owned startup work before releasing it.

Tests simulate a blocked local runtime and unresolved audio/voice enumeration;
the backend and initial display become available without those optional waits.
The startup cover still waits for a rendered frame and compositor settlement,
so this does not reveal the old UI or uninitialized model. Actual opening time
still depends on Qt startup, model size, textures and GPU shader compilation.

## Start with Windows

The current-user startup registration launches Sakura Companion.exe with
--windows-startup, which skips the interactive mode chooser and resumes saved
settings. Opening the launcher normally still shows the chooser. The Theme
checkbox reflects Windows Startup Apps disable state; explicitly ticking it
restores Sakura's own entry only. No administrator permission is required.
