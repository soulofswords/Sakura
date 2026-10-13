const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync('static/js/model-viewer.js', 'utf8').replace(/\r\n/g, '\n');
const body = source.match(/_animateCharacter\(delta, elapsed\) \{([\s\S]*?)\n    \}\n\n    _visibleModelBounds/)[1];
const animate = new Function('delta', 'elapsed', body);
function pose(vrm, activity = 'idle') {
    const bones = {};
    for (const key of ['leftArm', 'rightArm', 'leftElbow', 'rightElbow', 'leftWrist', 'rightWrist']) {
        bones[key] = { rest: { x: 0, y: 0, z: 0, order: 'XYZ' }, bone: { rotation: { set(x,y,z) { Object.assign(this,{x,y,z}); } } } };
    }
    const viewer = {model: {}, vrm, animationBones: bones, activity, talkBlend: 0, thinkBlend: 0, speechLevel: 0.5, expressionMorphs: {}, emotion: 'friendly'};
    for (let i=0;i<100;i++) animate.call(viewer, 1/60, 2);
    return bones;
}
const idle = pose({});
assert.ok(Math.abs(idle.leftArm.bone.rotation.z - Math.PI/2) < 0.25, 'VRM idle arm should be close to vertical');
assert.ok(Math.abs(idle.leftArm.bone.rotation.z + idle.rightArm.bone.rotation.z) < 0.001);
const speaking = pose({}, 'talking');
assert.ok(speaking.leftArm.bone.rotation.z < idle.leftArm.bone.rotation.z, 'talking should raise hand gently');
assert.ok(Math.abs(idle.leftElbow.bone.rotation.y) > 0, 'elbows should be softened');
assert.ok(pose(null).leftArm.bone.rotation.z < 0, 'PMX keeps original axis convention');
console.log('PASS: VRM relaxed arms, mirrored rest pose, speech gestures, soft elbows, PMX pose preserved');

