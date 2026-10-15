// Bound the complete output surface, independently of model format. Retained
// alpha buffers, depth and MSAA multiply this allocation beyond one RGBA image.
export function renderPixelRatio(width,height,requested,maxDimension=8192){
    width=Math.max(1,Number(width)||1);height=Math.max(1,Number(height)||1);
    const ratio=Math.max(.1,Number(requested)||1);
    // PIXI rounds backing dimensions up; reserve one pixel on each axis so
    // its allocation stays inside the same limit as Three's rounded buffer.
    const budget=Math.max(.00001,Math.sqrt(4_000_000/(width*height))-1/Math.min(width,height));
    return Math.min(ratio,budget,maxDimension/Math.max(width,height));
}
