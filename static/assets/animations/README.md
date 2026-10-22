# Hand Raising greeting

Derived from the user-provided `C:/Users/gaura/Downloads/Hand Raising.fbx`.
The original FBX is preserved in place; a working copy is in tools/animation-sources.
Source clip: mixamo.com, 4.066667 seconds, sampled at 30 fps.
The empty “Take 001” clip is ignored. Body-frame rest-relative rotations are retained
for spine/chest, neck/head, shoulders, arms, wrists and fingers. Root translation and
leg tracks are excluded so the character stays in its app position.

Replaces the previous procedural greeting wave. Runtime converts these rotations
into each target rig's bind frame, plays once with the first greeting speech phrase,
and blends back to the resting pose. This asset is user supplied; no new license
or redistribution rights are claimed here.

Retarget revision: source bind-direction alignment compensates for PMX A-pose versus Mixamo T-pose. Exit blends to the captured relaxed pose, not the import pose.
