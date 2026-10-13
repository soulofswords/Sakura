const fs = require('node:fs');
const assert = require('node:assert/strict');
const source = fs.readFileSync('static/js/model-viewer.js', 'utf8').replace(/\r\n/g, '\n');
const method = name => new Function(...(name === '_animateEyeTracking' ? ['delta'] : name === 'setEyeTrackingTarget' ? ['x', 'y'] : []),
    source.match(new RegExp(name + '\\([^)]*\\) \\{([\\s\\S]*?)\\n    \\}'))[1]);
const rotations = [];
const viewer = { animationBones: { leftEye: { rest: { x: 0, y: 0, z: 0, order: 'XYZ' },
    bone: { rotation: { set: (...values) => rotations.push(values) } } } } };
method('setEyeTrackingTarget').call(viewer, 5, -5);
for (let i = 0; i < 100; i++) method('_animateEyeTracking').call(viewer, 0.016);
assert.ok(Math.abs(rotations.at(-1)[0]) <= 0.12);
assert.ok(Math.abs(rotations.at(-1)[1]) <= 0.18);
method('clearEyeTracking').call(viewer);
for (let i = 0; i < 100; i++) method('_animateEyeTracking').call(viewer, 0.016);
assert.ok(Math.abs(rotations.at(-1)[1]) < 0.001);
const shouldAutoBlink = method('_shouldAutoBlink');
assert.equal(shouldAutoBlink.call({userTracking:false,vtuberTrackingMode:false}),true);
assert.equal(shouldAutoBlink.call({userTracking:true,vtuberTrackingMode:false}),false);
assert.equal(shouldAutoBlink.call({userTracking:false,vtuberTrackingMode:true}),false);
console.log('PASS: PMX eye rotation bounds and neutral reset; idle blink stays off during VTuber tracking');
const EyeTracking = new Function(fs.readFileSync('static/js/eye-tracking.js','utf8')
    .replace('export default class EyeTracking','class EyeTracking') + '; return EyeTracking;')();
const listeners = new Map();
global.window = {innerWidth:1000,innerHeight:500,addEventListener:(event,fn)=>listeners.set(event,fn),removeEventListener:event=>listeners.delete(event)};
global.document = {addEventListener(){},removeEventListener(){}};
const useCursor = method('_shouldUseCursorGaze');
for (const mode of ['gemini','local','vtuber']) {
    const active = {userTracking:mode==='vtuber',setEyeTrackingTarget:method('setEyeTrackingTarget'),clearEyeTracking:method('clearEyeTracking')};
    const tracker = new EyeTracking(active,()=>{});
    tracker.start(); assert.equal(active.eyeTrackingEnabled,true);
    assert.equal(useCursor.call(active),true,`${mode} must allow cursor gaze when enabled`);
    listeners.get('pointermove')({clientX:1000,clientY:0});
    assert.deepEqual(active.eyeTrackingTarget,{x:1,y:-1});
    tracker.stop(); assert.equal(active.eyeTrackingEnabled,false);assert.equal(active.eyeTrackingTarget,null);
    assert.equal(useCursor.call(active),mode!=='vtuber','VTuber must resume camera gaze when cursor tracking stops');
}
console.log('PASS: eye toggle starts, follows the cursor and stops in Gemini, Local LLM and active VTuber tracking');
