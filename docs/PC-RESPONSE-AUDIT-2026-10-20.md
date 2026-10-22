# PC Companion response-path audit — 20 October 2026

Scope: current source and owner-local Sakura Companion under F:\AI\assistant. No Windows installer was rebuilt, no app was launched/controlled, no real microphone/camera used, and no user timers/apps were changed.

Findings and changes:
- PC already routes reminders before app opening and supports compound spoken timer durations. Confirmed with temporary reminder stores; no need to copy the mobile timer implementation.
- Added missing date variants and typographic apostrophe normalization: What's today's date, What’s today’s date, What day is today, current date.
- Added a weather-scoped city parser: weather Mumbai, weather Mumbai right now, and polite phrasing containing an earlier “for me”. Trailing now/please/punctuation no longer becomes part of the city name. Existing explicit-date/16-day horizon behaviour remains.
- Explicit current weather/temperature requests fetch and speak only current conditions instead of three days of forecast. Existing generic forecasts and dated forecasts retain their daily results.
- Weather/news requests use bounded 3-second connection and 5-second read timeouts. These are per-operation limits, not a strict complete-task deadline.
- Topic-before-news phrasing, such as technology news, now uses the topic search rather than general headlines. News definition questions stay ordinary conversation. Source labels and publication freshness checks remain.
- Deterministic utilities skip screen capture, avatar readback and camera snapshots before submitting to the backend. Visual questions such as weather on my screen retain their capture/model path instead of becoming unrelated live lookups.
- Browser opening handles OS launch errors honestly. The macOS installed-app branch also returns failure if its launch process cannot start. A process/shell launch acceptance is not a guarantee the external app finished loading.

Validation:
- PASS: 37 Python tests covering new audit cases and existing commands, reminders, speech updates, weather dates and chat routing.
- PASS: utility capture bypass, visual-question retention, wake controls, startup presentation and continuous screen-capture checks.
- LIVE PC current weather in Mumbai: 1.23 seconds, successful Open-Meteo current conditions.
- LIVE PC latest technology news: 0.69 seconds, recent sourced headlines returned.
- Refreshed local Companion using tools/create-local-products.py --edition companion; app identity/import checks passed.

Real microphone, native launch UI and cloud/local model-generation performance were not benchmarked. Speech synthesis/provider response time still varies; the measured live results are specific to this development connection.
Restart Companion to load the changes. Windows release installers/GitHub releases remain unchanged.
