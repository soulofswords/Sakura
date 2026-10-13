// Chat Reader has a gentle weight shift, independent of speech and webcam
// retargeting. It never enables the companion's conversational hand gestures.
export function chatReaderLean(owner, delta) {
    if (owner.userTracking) { owner.chatReaderMotion = null; return null; }
    if (!owner.chatReaderActive && !owner.chatReaderMotion) return null;
    const motion = owner.chatReaderMotion ||= {time: 0, blend: 0};
    const dt = Math.max(0, Math.min(.1, Number(delta) || 0));
    motion.time += dt;
    motion.blend += (Number(Boolean(owner.chatReaderActive)) - motion.blend) * (1 - Math.exp(-dt / .5));
    const lean = Math.sin(motion.time * .65) * .035 * motion.blend;
    if (!owner.chatReaderActive && motion.blend < .0001) { owner.chatReaderMotion = null; return 0; }
    return lean;
}

export function applyChatReaderLean(owner, delta) {
    const lean = chatReaderLean(owner, delta);
    if (lean === null) return false;
    for (const [key, factor] of [['torso', 1], ['chest', -.2], ['neck', -.15], ['head', -.15]]) {
        const entry = owner.animationBones?.[key];
        if (!entry?.rest) continue;
        entry.bone.rotation.copy(entry.rest);
        entry.bone.rotation.z += lean * factor;
    }
    if (owner.physics) owner.physics.allowIdleSleep = false;
    return true;
}
