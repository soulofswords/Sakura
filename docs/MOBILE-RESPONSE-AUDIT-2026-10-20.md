# Sakura Mobile 0.3.13 — response-path audit

- Common polite prefixes, curly apostrophes, spacing and trailing please now normalize before direct command matching.
- Expanded native time/date phrases, including What time is it, Can you please tell me the time, and What's today's date. These bypass cloud AI and GPS.
- Fixed command priority: Start a five-minute timer previously matched start/open-app handling before the timer parser. Timers/alarms now run first.
- Timers accept spoken English numbers through 69, numeric durations, timer-for-duration and duration-timer forms. Alarms accept basic spoken hour forms such as three pm. Existing duration/time validation and visible Android clock confirmation remain. Complex multi-unit durations, recurring alarms and spoken minute phrases are not added by this patch.
- App and clock opening now wait for Android's launch result and report failure instead of swallowing exceptions and claiming success. A successful clock launch does not claim an alarm/timer was saved without user confirmation.
- Casual live-news requests and topical news use native Google News RSS with bounded 8-second connect/read timeouts and 2-minute per-query cache. Unavailable feeds produce an explicit failure, not unverified model-generated headlines. General feed uses India/English, with no GPS lookup.
- Ordinary chat keeps the previous no-blocking-GPS fix; explicit current weather and nearby requests retain their direct data paths. User-selected cloud voice synthesis and genuine AI generation still depend on their providers and connection.

Validation: Java command-rule cases and source guards passed for polite time/date, spelled/compound timers, timer/app precedence, spoken alarm and news/definition distinctions. Google News RSS returned HTTP 200 with item entries during a PC live endpoint check. Android Java/R8/signature/archive and packaged browser regressions passed. Actual phone app launches, clock UI, calls and speech-service latency still require device testing. No real microphone/camera/GPS was accessed.

Install over Sakura Mobile. App/package/signing identity and saved offline pack unchanged.
SHA256: acfdc0e7385615959b41a59e0a7e3639faf016cf8f9c198bc1439384e32a3bde
