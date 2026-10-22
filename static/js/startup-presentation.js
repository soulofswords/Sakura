// Reveal the initial surface only after settings and a complete renderer frame.
// Later model switches retain their existing last-frame presentation cover.
export async function finishStartupPresentation(viewer) {
    try {
        viewer?._renderFrame();
        // One startup synchronization only: finish pending uploads/draws
        // before revealing the native surface or loading Qwen onto the GPU.
        const gl=viewer?.live2d?.app?.renderer?.gl||viewer?.renderer?.getContext?.();
        gl?.finish?.();
        // Chromium can suspend requestAnimationFrame while a window is
        // minimized. Never leave the whole startup presentation waiting on a
        // frame that cannot be scheduled.
        await Promise.race([
            new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))),
            new Promise(resolve => setTimeout(resolve, 800)),
        ]);
    } finally {
        document.documentElement.classList.remove('sakura-starting');
    }
    fetch('/api/renderer/ready',{method:'POST'}).catch(()=>{});
}
