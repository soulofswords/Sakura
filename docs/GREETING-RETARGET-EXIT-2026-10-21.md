# Greeting arm retarget/exit repair — 21 October 2026

User reported hands moving all over the place and requested direct PC inspection. Selected the open Sakura Companion via the Windows computer-use tool, identified TDA Ririka Momobami the Vice President, and sent hello twice. Those initial native snapshots did not capture the raised portion. Reproduced the full FBX lifecycle against that exact model in a timed headless production viewer.

Confirmed the fade-out error: the model lowered the arm at the end of the source clip, then both arms spread toward its imported A-pose before snapping back to Companion idle. At 5.8 seconds the normalized wrist height was -0.617 (arms spread), instead of its relaxed -0.983. ImportedGreeting.apply used the bind/rest quaternion as the fade origin, and ModelDance.stop overwrote the restored pose with that same import pose.

Fixed fade and immediate restore to use the captured pre-animation relaxed pose. Added source bind-direction samples and per-bone longitudinal alignment so Mixamo T-pose arm/elbow/wrist/finger directions compensate for PMX A-pose and VRM orientation differences before rotation transfer. Source animation and normal physics preserved; no procedural greeting replacement. Re-baked compact JSON with source hash and cache version fbx89.

After repair, Ririka normalized wrist height was approximately -0.970 at 4.4 s and -0.983 at 5.8 s, remaining down through return to idle. Timed screenshots inspected. Unit tests cover fade weight zero restoring the captured pose, finite transforms, unchanged limb lengths, loading/retry and model/mode guards.

During native restart, the close callback blocked while synchronously waiting for WebEngine JS on the GUI thread. Changed session-end notification to a daemon worker. The already-blocked old owned desktop process was stopped, its launcher notice dismissed, and the existing Companion launcher reopened in Local LLM mode. Sent hello through native chat again; observed the lowered/settled phases without the previous spread. No microphone/camera enabled. Both local product copies refreshed; Companion left open on the same Ririka model. No installers/APK/GitHub release created.
