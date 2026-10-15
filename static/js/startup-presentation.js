// Reveal the initial surface only after settings and a complete renderer frame.
// Later model switches retain their existing last-frame presentation cover.
export async function finishStartupPresentation(viewer) {
    try {
        viewer?._renderFrame();
        // One startup synchronization only: finish pending uploads/draws
        // before revealing the native surface or loading Qwen onto the GPU.
        const gl=viewer?.live2d?.app?.renderer?.gl||viewer?.renderer?.getContext?.();
        gl?.finish?.();
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    } finally {
        document.documentElement.classList.remove('sakura-starting');
    }
    fetch('/api/renderer/ready',{method:'POST'}).catch(()=>{});
}
