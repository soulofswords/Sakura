# Hindi conversation repair — 21 October 2026

- Selecting a Hindi voice selects Hindi replies and Hindi (`hi`) microphone recognition; Hinglish also accepts Hindi microphone input.
- Added Hindi and Romanized Hindi intent handling for language ability, greetings and avatar presentation, including the reported `app ladke ho kya ladki` spelling.
- Hindi chat uses a simpler, grounded persona instead of the large playful English personality checklist. Local Hindi sampling uses lower temperature.
- Rejects the specific nonsensical Hindi phrases reported by the user instead of accepting any Devanagari text as valid Hindi. Language correction now answers the latest question rather than faithfully translating an unrelated draft.
- Shared generation changes apply to local and cloud providers, Companion and AI VTuber; no cloud key was used for testing.

Validation: 39 relevant unit tests passed. Live local Qwen3-VL 4B test results are in `audit-results/hindi-conversation-verified.json`. The reported common intents now return grounded answers. General Hindi remains limited by this small model: live tests still produced awkward grammar and irrelevant suggestions. Prompt changes and narrow validators cannot guarantee semantic correctness; this is not a claim that all Hindi quality issues are solved. A larger Hindi-capable model or cloud provider should be evaluated separately. No microphone/camera recording was made.

Updated local product files require closing and reopening Sakura to load the changed Python modules. No installer or GitHub release built in this task.
