const point3 = value => Array.isArray(value) && value.length >= 3 && value.slice(0, 3).every(Number.isFinite)
    ? {x: value[0], y: value[1], z: value[2]} : null;

/** Convert the Ultraleap v6 JSON frame into Sakura's existing 21-point hand format. */
export function mapLeapFrame(frame, pose) {
    const hands = Array.isArray(frame?.hands) ? frame.hands : [];
    const pointables = Array.isArray(frame?.pointables) ? frame.pointables : [];
    return hands.slice(0, 2).map(hand => {
        const side = String(hand.type || '').toLowerCase();
        const wrist = point3(hand.wrist || hand.palmPosition);
        const sideIndex = side === 'left' ? 15 : side === 'right' ? 16 : -1;
        const wristImage = sideIndex >= 0 ? pose?.landmarks?.[sideIndex] : null;
        if (!wrist || !wristImage) return null;
        const wristWorld = pose?.world?.[sideIndex] || {x: 0, y: 0, z: 0};
        const imageScale = 0.00068;
        const worldScale = 0.001;
        const toImage = raw => {
            const p = point3(raw);
            if (!p) return null;
            return {x: wristImage.x + (p.x - wrist.x) * imageScale,
                y: wristImage.y - (p.y - wrist.y) * imageScale,
                z: wristImage.z + (p.z - wrist.z) * imageScale, visibility: hand.confidence ?? 1};
        };
        const toWorld = raw => {
            const p = point3(raw);
            return p ? {x: wristWorld.x + (p.x - wrist.x) * worldScale,
                y: wristWorld.y - (p.y - wrist.y) * worldScale,
                z: wristWorld.z + (p.z - wrist.z) * worldScale} : null;
        };
        const landmarks = Array(21).fill(null), world = Array(21).fill(null);
        landmarks[0] = toImage(hand.wrist || hand.palmPosition);
        world[0] = toWorld(hand.wrist || hand.palmPosition);
        for (const finger of pointables.filter(p => p.handId === hand.id && Number.isInteger(p.type) && p.type >= 0 && p.type <= 4)) {
            const offset = finger.type === 0 ? 1 : 5 + (finger.type - 1) * 4;
            const raw = finger.type === 0
                ? [finger.carpPosition || finger.mcpPosition, finger.mcpPosition, finger.pipPosition, finger.tipPosition || finger.btipPosition]
                : [finger.mcpPosition || finger.carpPosition, finger.pipPosition, finger.dipPosition || finger.pipPosition, finger.tipPosition || finger.btipPosition];
            raw.forEach((position, i) => {
                landmarks[offset + i] = toImage(position);
                world[offset + i] = toWorld(position);
            });
        }
        // Ignore incomplete hardware frames instead of feeding NaNs to the rig.
        if (landmarks.some(p => !p) || world.some(p => !p)) return null;
        const confidence = Number.isFinite(hand.confidence) ? hand.confidence : 0.8;
        return {side, confidence, landmarks, world};
    }).filter(Boolean);
}
