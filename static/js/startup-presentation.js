// Reveal the initial surface only after settings and a complete renderer frame.
// Later model switches retain their existing last-frame presentation cover.
export async function finishStartupPresentation(viewer) {
    try {
        viewer?._renderFrame();
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    } finally {
        document.documentElement.classList.remove('sakura-starting');
    }
}
