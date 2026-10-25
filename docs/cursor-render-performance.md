# 3D cursor lag: measured cause and correction

Both PMX and VRM used `_hitModelAt()` for hover/drag-cursor feedback. That path recomputed skinned bounds and CPU-skinned triangles on each check. Rate limiting the checks still left large stalls; changing gaze smoothing did not address this cause.

An isolated Edge/D3D11 benchmark used the real model renderer, real model assets, and RTX 3080. No camera, microphone, or AI requests were made. The viewport was 1920 x 1080, drawing buffer 2400 x 1350.

| Case | Render FPS | Hover check average |
| --- | ---: | ---: |
| VRM 1439626354518702295, no mouse movement | 180 | n/a |
| Same VRM, old CPU hover picking | 7 | 137.12 ms |
| Same VRM, one-pixel GPU picking | 180 | 2.98 ms |
| PMX Ananta/Ringo/Ringo, GPU picking | 180 | 2.04 ms |

These are benchmark results, not a native window FPS guarantee. The fix keeps the original materials/texture alpha, excludes other avatars, and restores render target, viewport, scissor, clear color and background. Pointer-down checks a fresh GPU pixel; empty stage and transparent holes do not begin model dragging. The hover icon remains rate-limited, independently from per-event cursor gaze.

Deployed surgically to source, installed Companion, and installed VTuber. Renderer cache key: cursor-gpu6.

Verification: `node tests/cursor-gpu-picking.cjs`, `node tests/model-drag-hit.cjs`, `node tests/eye-tracking.cjs`, `node tests/cursor-stream.cjs`, `node tests/vrm-gloss.cjs`. Reproduce GPU profiling with `node tools/profile-cursor-render.cjs` or pass a model path relative to the installed model root.
