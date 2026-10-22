# Emoji speech cleanup — 21 October 2026

The existing final TTS cleaner already removed basic emoji such as the reported cat/explosion pair. Strengthened the shared filter to handle flags, keycaps, joined emoji, skin-tone modifiers, selectors and tag sequences, and remove Markdown quote prefixes without removing numeric comparisons. Deferred chat now returns cleaned speech_reply before frontend phrase splitting, while reply retains its visual chat formatting. Final TTS cleanup remains in place for chat reader, normal speech and RVC synthesis paths.

Tests cover the reported text, combined emoji sequences, emoji-only replies (no synthesis), preservation of Hindi, temperatures, multiplication and comparisons, and both deferred API and final synthesis boundaries. Direct laugh remains a recorded-performance command, bypassing TTS. Both local PC products refreshed; an already running process must be restarted to load updated Python modules. No installer or GitHub release created.
