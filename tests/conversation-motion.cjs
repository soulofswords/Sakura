const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync('static/js/model-viewer.js', 'utf8').replace(/\r\n/g, '\n');
const animate = new Function('delta', 'elapsed', source.match(/_animateCharacter\(delta, elapsed\) \{([\s\S]*?)\n    \}\n\n    _visibleModelBounds/)[1]);
function make() {
    const bone = () => ({rotation: {set(x,y,z) {Object.assign(this,{x,y,z});}}});
    const animationBones = Object.fromEntries(['torso','chest','head','neck','leftArm','rightArm','leftElbow','rightElbow','leftWrist','rightWrist'].map(key => [key, {bone:bone(),rest:{x:0,y:0,z:0,order:'XYZ'}}]));
    return {model:{}, animationBones, talkBlend:0,thinkBlend:0,speechLevel:.8,activity:'talking',emotion:'friendly', expressionMorphs:{},
        conversationFingers:[{bone:bone(),side:'left',finger:1,segment:0,rest:{x:0,y:0,z:0,order:'XYZ'},curl:0}]};
}
function run(hz) {const v=make();for(let i=0;i<hz*7;i++) animate.call(v,1/hz,i/hz);return v;}
const slow=run(30),fast=run(120);
for(const key of Object.keys(slow.animationBones)) for(const axis of ['x','y','z']) {
    assert.ok(Math.abs(slow.animationBones[key].bone.rotation[axis]-fast.animationBones[key].bone.rotation[axis])<.02, 'Frame-rate-independent '+key);
}
assert.ok(fast.conversationMotion.beat>=2, 'Gestures progress beyond a single repeated stroke');
assert.notEqual(fast.animationBones.leftWrist.bone.rotation.z, -fast.animationBones.rightWrist.bone.rotation.z, 'Hands have asymmetric intent');
assert.ok(fast.conversationFingers[0].curl>0 && fast.conversationFingers[0].curl<.25, 'Fingers rest with bounded curvature');
fast.activity='idle';fast.speechLevel=0;
for(let i=0;i<360;i++) animate.call(fast,1/60,7+i/60);
assert.ok(fast.talkBlend<.001);
assert.ok(Math.abs(fast.animationBones.leftWrist.bone.rotation.z+.045)<.001, 'Hand settles after speaking');
const tracking=make();let calls=0;tracking.userTracking=true;tracking.avatarRetarget={apply(){calls++;}};
animate.call(tracking,1/60,0);assert.equal(calls,1);assert.equal(tracking.conversationMotion,undefined,'Tracking mode bypasses AI motion');
console.log('PASS: alternating strokes, soft finger poses, 30/120 Hz equivalence, speech recovery and tracking isolation');
