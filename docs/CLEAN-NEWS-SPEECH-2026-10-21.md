# Clean news speech — 2026-10-21

News speech keeps the current bulletin date and time in IST, followed by the headlines. Spoken versions omit raw source URLs, per-article ISO publication timestamps, repeated publisher suffixes, and the technical "retrieved now" introduction. Original cited reply remains in the chat. Desktop cleans the complete news reply before phrase splitting, plus speech synthesis cleanup; local/cloud modes share the behavior. Mobile provider speech and background Android speech fallback both use the clean news text.

Validation: Python speech/voice/news/endpoint tests passed; local/Gemini/OpenAI endpoint cases preserve cited chat and provide a clean speech reply. Actual Java news speech/query/time tests passed. JavaScript syntax passed. Local PC Companion refreshed. Sakura Mobile 0.3.16 built, obfuscated, signed and package verification passed. Windows installers not rebuilt; GitHub unchanged.
