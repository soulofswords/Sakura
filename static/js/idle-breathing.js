// Add a small chest rotation, never a torso scale or root translation.
export function restoreIdleBreathing(viewer) {
    for (const entry of viewer._idleBreathOffsets || []) {
        if (Math.abs(entry.bone.rotation.x - entry.after) < 1e-6) entry.bone.rotation.x = entry.before;
    }
    viewer._idleBreathOffsets = [];
}
export function applyIdleBreathing(viewer, delta, elapsed) {
    if (!viewer.model || (viewer.userTracking && !viewer.companionTracking) || viewer.dance?.active || viewer.chatReaderActive || viewer.chatReaderMotion
        || (viewer.activity && viewer.activity !== 'idle') || viewer.remoteCollab) return;
    viewer._idleBreathTime = (viewer._idleBreathTime || 0) + Math.min(.05, Math.max(0, delta));
    const fade = Math.min(1, viewer._idleBreathTime / 1.2);
    const wave = Math.sin(elapsed * Math.PI * 2 / 4.8) * fade;
    const chest = viewer.animationBones?.chest || viewer.animationBones?.torso;
    if (!chest?.bone) return;
    const before = chest.bone.rotation.x;
    chest.bone.rotation.x += wave * .009;
    viewer._idleBreathOffsets = [{bone:chest.bone, before, after:chest.bone.rotation.x}];
}
