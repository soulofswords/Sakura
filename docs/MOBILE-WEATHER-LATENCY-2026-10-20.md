# Sakura Mobile 0.3.12 — simple-request latency and current weather

- Removed the mandatory fresh GPS request before every ordinary AI message when location is enabled. It could add up to 18 seconds plus reverse-geocoding latency even for unrelated chat. Ordinary chat now uses only an already-fresh in-memory area context; explicit location/nearby requests still refresh GPS.
- Greetings have a direct short answer using the selected Sir/Ma’am/no-title preference. Time/date, device commands and named current-weather requests execute before GPS and cloud AI.
- Added current-weather city parsing for current weather in Mumbai, weather in Mumbai right now, weather Mumbai and Mumbai ka mausam. Trailing now/today/please terms are removed from the geocoding query. Explicit cities do not require phone GPS, including background wake mode.
- Direct Open-Meteo request includes temperature, humidity, weather condition code and source/local update time. Mumbai/Bombay uses a public city-centre coordinate without an extra geocoding round trip. Other city geocodes are cached in memory; successful coordinate weather results are cached for 5 minutes with their actual update time.
- Weather network connections have bounded 5-second connect/7-second read timeouts rather than the shared 90-second AI timeout. Service errors give an explicit unavailable/retry message and do not ask the AI to invent current weather.

Validation: actual Java weather/intent cases and command-before-GPS guards passed; Android Java/R8/signature/archive checks and packaged UI regression passed. Both public Mumbai geocoding and current-weather API calls succeeded from the development PC on 20 October 2026. No real phone GPS/microphone was used. Phone-network, provider generation and cloud voice synthesis latency still depend on the device/service; no instant-response guarantee.

Install over Sakura Mobile; offline wake pack remains installed.
SHA256: 483334dc7b527850e11d71df52716ea95e3efcd9a6c16d02f01b70c3edb9d23c
