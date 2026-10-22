# Chest-tap speech/animation alignment — 21 October 2026

The reported “Taps chest gently” line was generated narration, not an animation command. Added an allowlisted chest-tap motion for supported 3D avatar rigs. Conversational heart/heartbeat statements can select it when the answer responds in that context; explicit chest-tap requests also select it. The normal conversation and API provider remain unchanged. Medical mentions, negations, quoted speech and unrelated heart references do not trigger it.

The PC frontend advertises the capability only for a rigged PMX/VRM with chest, right arm, elbow and wrist. The motion starts with the first audio phrase (or on voice failure for text-only presentation), moves the right hand toward the upper chest with position-based IK, turns the palm inward using authored finger roots when available, performs one gentle approach/contact/release, and blends back to neutral. Model changes and face tracking cancel it. Live2D is excluded because arbitrary arm poses cannot be created without authored parameters.

Removed recognized chest-tap stage directions from spoken/chat output, including the bare emoji-prefixed reported format, without stripping ordinary sentences about the chest.

Validation: endpoint tests for local/Gemini/OpenAI capability gating; parser false-positive and narration-cleanup checks; pose lifecycle/finite-transform tests; real Ringo PMX and VRM browser render tests verified the wrist reaches the chest region and the motion completes/cancels correctly. Screenshots and numerical reports in audit-results/chest-tap-*. No camera or microphone was accessed. Local products refreshed separately; restart to load changes. No installer or GitHub update requested/performed.
