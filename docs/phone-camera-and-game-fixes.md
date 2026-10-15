Phone connection pairs controls only. The Sakura Mobile Companion tab now has
Share camera with Companion: sends bounded JPEG frames to the paired PC, with
no face-tracking start. Start camera tracking remains a separate VTuber action.
The two camera uses are mutually exclusive and off by default. Backgrounding
the phone app stops both. Companion viewing can send the current image to the
PC's selected vision provider for a reply; Local mode keeps inference local.
The standalone Sakura VTuber PC rejects Companion camera-image requests.

Game mode keeps the selected AI provider, model and context instead of forcing
2B/2048 on entry and 4B on exit. It enables screen viewing/reactions and retains
microphone input. AI VTuber still intentionally excludes microphone input.
Result watching checks captured frames on a four-second minimum interval, after
the prior inference completes; conversation and recording take priority. Visible
results can animate during the normal post-chat comment cooldown. The same result
is latched and rate-limited. Vision task instructions are separate from the
personality so small-context compaction does not replace them with chat defaults.
This is sampled detection, not a guarantee that every short banner is observed.

Companion minimize is now idempotent compact mode; only tracking/standalone VTuber
uses actual OS minimize. Native restoration clears both maximized and iconic state.
Tests cover mode transitions, phone endpoint authorization, result metadata,
classification protocol retention, camera source isolation, and native restoration.
Synthetic VICTORY and DEFEAT images were recognized by the installed local model.
Live Valorant and physical Android camera operation still require device testing.
