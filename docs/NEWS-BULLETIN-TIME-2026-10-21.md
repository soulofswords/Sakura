# News bulletin time — 2026-10-21

Both Windows Companion and Sakura Mobile prepend the current date and time in IST before reciting a successful news bulletin. This is the bulletin time, not a claim that all articles were published at that time. Explicit "news for Mumbai" overrides the saved news area. The desktop lookup is shared by Local LLM, Gemini and OpenAI; mobile native lookup precedes cloud generation and also works for background wake requests. Live news requires internet even with a local language model.

Validation: PC Python news/endpoint tests including all three provider routes; actual Java rules including date rollover from UTC to IST; Android location/command regression tests. Sakura Mobile 0.3.15 built and signed with existing identity, build/archive/Unicode/model-exclusion checks passed. Local Windows Companion refreshed; no Windows installer rebuild or GitHub push.
