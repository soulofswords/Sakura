const fs = require('node:fs');
const assert = require('node:assert/strict');
const source = fs.readFileSync('static/js/model-viewer.js', 'utf8').replace(/\r\n/g, '\n');
const restore = new Function(source.match(/_restoreCursorHeadPose\([^)]*\) \{([\s\S]*?)\n    \}/)[1]);
const method = name => {
    const fn = new Function(...(name === '_animateEyeTracking' ? ['delta'] : name === 'setEyeTrackingTarget' ? ['x', 'y'] : []),
        source.match(new RegExp(name + '\\([^)]*\\) \\{([\\s\\S]*?)\\n    \\}'))[1]);
    return function(...args){ this._restoreCursorHeadPose ||= restore; this.limitEyeRotation ||= new Function('pitch','yaw',source.match(/limitEyeRotation\(pitch,yaw\) \{([\s\S]*?)\n    \}/)[1]); return fn.apply(this,args); };
};
const configureGaze = new Function('vrm', source.slice(source.indexOf('        const lookAtApplier = vrm.lookAt?.applier;'),source.indexOf('        VRMUtils.rotateVRM0(vrm);')));
for(const expressionBased of [false,true]) {
    const applier={constructor:{type:expressionBased?'expression':'bone'}};
    for(const key of ['rangeMapHorizontalInner','rangeMapHorizontalOuter','rangeMapVerticalDown','rangeMapVerticalUp'])applier[key]={outputScale:expressionBased?1:8};
    if(expressionBased)applier.expressions={};
    configureGaze({lookAt:{applier}});
    assert.equal(applier.rangeMapHorizontalOuter.outputScale,expressionBased?1:30,'Expression gaze weights must not be changed into degrees');
}
const rotations = [];
const viewer = { animationBones: { leftEye: { rest: { x: 0, y: 0, z: 0, order: 'XYZ' },
    bone: { rotation: { set: (...values) => rotations.push(values) } } } } };
method('setEyeTrackingTarget').call(viewer, 1, -1);
for (let i = 0; i < 100; i++) method('_animateEyeTracking').call(viewer, 0.016);
const [pitch, yaw] = rotations.at(-1);
assert.ok(Math.abs(pitch + 0.20) < 0.01, `pitch should reach -0.20 rad, got ${pitch}`);
assert.ok(Math.abs(yaw - 0.30) < 0.01, `yaw should reach 0.30 rad, got ${yaw}`);
method('clearEyeTracking').call(viewer);
for (let i = 0; i < 100; i++) method('_animateEyeTracking').call(viewer, 0.016);
assert.ok(Math.abs(rotations.at(-1)[1]) < 0.001);
const shouldAutoBlink = method('_shouldAutoBlink');
assert.equal(shouldAutoBlink.call({userTracking:false,vtuberTrackingMode:false}),true);
assert.equal(shouldAutoBlink.call({userTracking:true,vtuberTrackingMode:false}),false);
assert.equal(shouldAutoBlink.call({userTracking:false,vtuberTrackingMode:true}),false);
console.log('PASS: PMX eye rotation reaches visible bounds and resets to neutral; idle blink stays off during VTuber tracking');
const lookAt = {yaw: 0, pitch: 0, autoUpdate: true};
const vrmViewer = {animationBones: {}, vrm: {lookAt}};
method('setEyeTrackingTarget').call(vrmViewer, 1, -1);
for (let i = 0; i < 100; i++) method('_animateEyeTracking').call(vrmViewer, 0.016);
assert.equal(lookAt.autoUpdate, false, 'VRM gaze must drive three-vrm lookAt directly');
assert.ok(Math.abs(lookAt.yaw - 48) < 0.01, `VRM yaw should reach 48 deg, got ${lookAt.yaw}`);
assert.ok(Math.abs(lookAt.pitch + 36) < 0.01, `VRM pitch should reach -36 deg, got ${lookAt.pitch}`);
method('setEyeTrackingTarget').call(vrmViewer, -1, 1);
for (let i = 0; i < 100; i++) method('_animateEyeTracking').call(vrmViewer, 0.016);
assert.ok(Math.abs(lookAt.yaw + 48) < 0.01, `VRM yaw should mirror, got ${lookAt.yaw}`);
assert.ok(Math.abs(lookAt.pitch - 36) < 0.01, `VRM pitch should mirror, got ${lookAt.pitch}`);
method('clearEyeTracking').call(vrmViewer);
assert.deepEqual([lookAt.yaw, lookAt.pitch], [0, 0], 'clearing must recentre the VRM gaze');
for (const key of ['rangeMapHorizontalInner', 'rangeMapHorizontalOuter', 'rangeMapVerticalDown', 'rangeMapVerticalUp'])
    assert.ok(source.includes(`'${key}'`), `loaded VRMs must widen ${key} so tracking stays visible`);
assert.ok(source.includes('outputScale = 30'), 'VRM look-at output range must be widened');
assert.ok(source.includes('/ 0.006'), 'pupils must land within ~3 frames so the gaze does not trail the cursor');
assert.ok(source.includes('/ 0.016'), 'the head must trail the eyes at glance speed instead of snapping');
const headBone = { rotation: { x:0,y:0,z:0,order:'XYZ',set(x, y, z) { this.x = x; this.y = y; this.z = z; } } };
const glide = {animationBones: {head: {rest: {x: 0, y: 0, z: 0, order: 'XYZ'}, bone: headBone}},
    vrm: {lookAt: {yaw: 0, pitch: 0, autoUpdate: true}}};
method('setEyeTrackingTarget').call(glide, 0.9, 0);
let eyeFrames = 0;
let headFrames = 0;
for (let i = 0; i < 60; i++) {
    method('_animateEyeTracking').call(glide, 1 / 60);
    if (!eyeFrames && glide.vrm.lookAt.yaw >= 0.9 * 48 * 0.95) eyeFrames = i + 1;
    if (!headFrames && headBone.rotation.y >= 0.9 * 0.30 * 0.95) headFrames = i + 1;
}
assert.ok(eyeFrames >= 1 && eyeFrames <= 2, `pupils should catch the cursor in ~3 frames, took ${eyeFrames}`);
assert.ok(headFrames >= 2 && headFrames <= 4, `head should trail the eyes over ~3 frames, took ${headFrames}`);
// Camera tracking must not silently disable cursor-driven head motion.
glide.userTracking=true;
restore.call(glide);
headBone.rotation.set(.12,-.08,.03);
method('setEyeTrackingTarget').call(glide,.7,-.4);
for(let i=0;i<120;i++)method('_animateEyeTracking').call(glide,1/60);
assert.ok(Math.abs(headBone.rotation.y-(-.08+.7*.30))<.001,'camera and cursor head offsets must coexist without drift');
assert.ok(Math.abs(headBone.rotation.x-(.12+.4*.15))<.001,'VRM pitch must use normalized humanoid axes');
method('clearEyeTracking').call(glide);
assert.ok(Math.abs(headBone.rotation.y+.08)<.001,'disabling cursor gaze restores the camera pose immediately');
assert.ok(Math.abs(headBone.rotation.x-.12)<.001);
console.log('PASS: VRM avatars swing the three-vrm lookAt in both eye directions');
const EyeTracking = new Function(fs.readFileSync('static/js/eye-tracking.js','utf8')
    .replace('export default class EyeTracking','class EyeTracking') + '; return EyeTracking;')();
const requests = [];
global.fetch = async (url, options) => {
    requests.push([url, options?.cache]);
    return { ok: true, json: async () => ({ x: 0.4, y: -0.6 }) };
};
const useCursor = method('_shouldUseCursorGaze');
(async () => {
    for (const mode of ['gemini','local','vtuber']) {
        const active = {userTracking:mode==='vtuber',setEyeTrackingTarget:method('setEyeTrackingTarget'),clearEyeTracking:method('clearEyeTracking')};
        const tracker = new EyeTracking(active,()=>{});
        tracker.start(); assert.equal(active.eyeTrackingEnabled,true);
        assert.equal(useCursor.call(active),true,`${mode} must allow cursor gaze when enabled`);
        await new Promise(resolve => setTimeout(resolve, 20));
        assert.deepEqual(active.eyeTrackingTarget,{x:0.4,y:-0.6},`${mode} must follow the screen cursor`);
        assert.deepEqual(requests.at(-1),['/api/cursor','no-store']);
        tracker.stop(); assert.equal(active.eyeTrackingEnabled,false);assert.equal(active.eyeTrackingTarget,null);
        assert.equal(useCursor.call(active),mode!=='vtuber','VTuber must resume camera gaze when cursor tracking stops');
        const seen = requests.length;
        await new Promise(resolve => setTimeout(resolve, 120));
        assert.equal(requests.length,seen,'stopping must cancel cursor polling');
    }
    console.log('PASS: eye toggle follows the screen cursor in Gemini, Local LLM and active VTuber tracking');
    global.fetch = async () => ({ ok: false, json: async () => ({}) });
    const active = {setEyeTrackingTarget:method('setEyeTrackingTarget'),clearEyeTracking:method('clearEyeTracking')};
    const tracker = new EyeTracking(active,()=>{});
    tracker.start();
    await new Promise(resolve => setTimeout(resolve, 1000));
    tracker.stop();
    assert.equal(active.eyeTrackingTarget,null,'a dead cursor endpoint must release the gaze instead of freezing it');
    console.log('PASS: an unavailable cursor endpoint releases the gaze instead of freezing it');
})();
