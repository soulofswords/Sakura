# Companion window presentation

October 14 startup follow-up: Windows Companion now adds `--disable-direct-composition` alongside full compositor swaps. ANGLE/D3D11 GPU model rendering remains enabled. This tests avoiding a second Windows surface presenter for Qt's layered alpha window; the exact cause of the intermittent squares is not yet proven. Restarted the native Gemini-mode app with Ringo, checked its loaded frame, compact transition and actual desktop transparency. Captured frames were clean; snapshot checks cannot establish that intermittent flicker is eliminated.

Gemini key check in the same session returned HTTP 200 for model access. Live generation returned HTTP 503 repeatedly; those requests were service failures rather than key rejection. No key values are recorded here.

The October 14 recording showed repeated shrinking copies of the character, and toolbar pixels persisting after the menu was clicked. The earlier transparent snapshot cover was insufficient on this native surface.

Companion retains the last completed WebGL drawing buffer, creates no saved-frame overlay, and resets the default framebuffer, full viewport and scissor state before presenting each 3D frame. The renderer clears and draws within the same render call. The initial attempt to discard the buffer prevented some stale frames but exposed a blank alpha canvas when native UI repainted between animation frames, especially around speech initialization. The VTuber product retains its previous presentation path. Windows Companion also requests full compositor swaps via `--ui-disable-partial-swap`, without disabling GPU acceleration.

The hamburger menu uses a fixed panel outside the titlebar layout. It closes on repeated click, Escape or outside click. Native drag handlers cannot intercept the button. Model/voice dropdowns use viewport positions to escape the scrolling panel's clipping. Controls remain available after maximizing.

The native retest reproduced the underlying problem: dismissed menu pixels remained beneath the animated avatar. Companion now gives the page an opaque background during normal use and switches its native page background to transparent together with the existing transparency toggle. Both the top-level window and child WebEngine view retain pywebview's alpha-capable surfaces; disabling child translucency or enabling automatic background fill breaks desktop transparency. A 30 Hz backing-store update runs only while transparency is enabled; normal mode uses Chromium's usual damage updates. Both transitions run on Qt's UI thread.

Checks cover framebuffer reset and product isolation, actual headless browser button clicks and dropdown bounds at 320/460/1100 pixels, model-switch races and syntax. Native launcher checks passed with the nankyocuplar Live2D model and Barbara PMX: minimize, hamburger open/close, Escape, zoom/movement redraw and character-only/control restoration. Dismissed controls and previous model frames no longer remained in the captured native window. The separately deployed VTuber files match their pre-change hashes.

Chromium switch source: https://chromium.googlesource.com/chromium/src/+/59.0.3071.82/ui/compositor/compositor_switches.cc

Speech-load retest: native Kokoro progress indicator is static to avoid a separate animated compositor layer. Restarted Companion, submitted hello in its chat, confirmed Kokoro ready via its status endpoint, and inspected response/rendering frames without blank patches. Voice initialization, playback race/cleanup, phrase scheduling, post-speech motion and model-switch tests passed. Point-in-time captures cannot prove every intermittent driver flash is gone.

Transparency correction: the first native check verified control hiding, but did not verify the desktop showing through. After restoring the child surface's original translucency and removing automatic background fill, the running PMX Companion visibly showed the underlying window through its background. Toggling back, opening/closing the hamburger menu, and toggling to transparency again all passed without retained menu pixels.
