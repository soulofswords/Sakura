# Companion timers and alarms

Typed or spoken commands use the same local handler in Gemini and local modes, without inference or internet. Examples:

- Make a 5 min timer.
- Set a five minute timer.
- Set a twenty five minute timer.
- Start a timer for 1 hour 30 minutes.
- Set an alarm for 3 PM / 15:00 / three PM tomorrow.
- Show my timers / list alarms.
- Cancel the timer / cancel all timers / cancel the alarm.
- Snooze the alarm (five minutes).

Alarm times use the PC's local timezone. An already-passed time defaults to tomorrow, with the calendar date explicitly confirmed. An explicitly passed time today is rejected. Date-based/weekly and recurring alarms are not implemented; requests containing weekdays or “on” are clarified instead of silently assigned to today.

Active reminders are stored in `reminders.json`, excluded from Git and distributed packages. Expiry state is durable and dismissal removes the reminder. Snooze schedules it five minutes ahead. Multiple reminders can be listed and cancelled by the displayed eight-character ID; without an ID, cancellation selects the most recently created matching reminder, preferring one already ringing. Keep Sakura open and the PC awake for on-time alerts. Closing the app or sleeping the PC prevents an on-time chime; overdue reminders appear when the app next runs. This does not install an operating-system wake task or background service.

The Companion UI polls locally once a second and shows a visible alert plus a generated chime, with Dismiss and Snooze controls. Alerts do not depend on Kokoro/RVC loading. Audio may require a user interaction under browser autoplay restrictions. Tracking-only and AI VTuber modes do not show Companion alerts; scheduled reminders stay saved.

Tests cover durations, word quantities, alarm time conversion, invalid inputs, persistence, expiry, snooze, cancellation, visible alert/dismiss handling and mode isolation.
