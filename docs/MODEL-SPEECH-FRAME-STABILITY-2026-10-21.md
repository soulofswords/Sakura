# Model switch / speech frame stability — 21 October 2026

Inspection found two concrete presentation gaps in the native Companion rendering path: saved-frame protection was bypassed during resize/quality changes, and `_prepareCompanionSurface` could remove a held frame before the replacement draw. A quality change during final model preparation could also schedule an early uncover. These can expose a cleared canvas during changes in layout or GPU preparation. Logs did not establish that these explain every intermittent black-square report.

The saved alpha frame now replaces (rather than overlays) the live canvas via the existing visibility CSS in Companion too. Only the release path removes it, and final shader/GPU preparation prevents early release. The block transition keeps ownership when already active, avoiding stacked covers. Both local product editions receive the shared viewer fix.

A separate issue: `_renderFrame` forwarded the entire wall-clock delta to VRM spring updates after CPU stalls. It now bounds simulation steps to 50ms (invalid/negative steps become zero), also used for PMX/Live2D updates. This prevents a slow speech-preparation/upload frame from becoming a large physics jump. It does not claim to fix all native graphics driver/compositor defects.

Validation:
- Model controls/presentation, GPU wait/cancellation, model loading races, and lip-sync tests passed.
- Six real Ananta/Arknights switches (Taffy, Arclight, Ardelia, Rossi) in Edge/ANGLE D3D11: no WebGL errors or context loss.
- Real PMX Ringo, VRM and MIU2022 Live2D speech playback, resize/quality redraw, and a simulated 220ms main-thread stall: finite bones, no WebGL errors or stuck frame covers. VRM and Live2D step maximum 0.05s. Results in `audit-results/speech-render-stability.json`.
- These are browser/runtime checks; the exact intermittent native Qt flicker was not visually reproduced in this run.

Local Companion and VTuber app files refreshed. Fully close and reopen to load the new viewer asset. No installer/release build in this task.
