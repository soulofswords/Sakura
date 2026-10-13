const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),THREE=require('../static/vendor/three/build/three.cjs');
const source=fs.readFileSync('static/js/avatar-retarget.js','utf8').replace(/^import .*;\r?\n/gm,'').replace(/export function /g,'function ').replace('export default class AvatarRetarget','class AvatarRetarget');
const ctx={THREE,performance};vm.runInNewContext(source+'\nthis.blink=glassesBlink;',ctx);
assert.equal(ctx.blink(.9,.25,.25,1),0,'Reflection score must not close a clearly open eye');assert.ok(ctx.blink(.2,.01,.25,1)>.95,'Measured eyelid closure wins despite weak score');assert.ok(ctx.blink(.8,null,.25,1)>.9,'Missing landmarks use scores');
const live=fs.readFileSync('static/js/live2d-viewer.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export default class Live2DViewer','class Live2DViewer');vm.runInNewContext(live+'\nthis.View=Live2DViewer;',ctx);
const values={},core={getParameterIndex(){return 0;},setParameterValueById(id,value){values[id]=value;}};
const v=Object.create(ctx.View.prototype);Object.assign(v,{filtered:{},values:{},eyeNeutral:{L:.25,R:.25},avatar:{internalModel:{coreModel:core}},neutral:new THREE.Euler(),owner:{userTracking:true,trackingMouthEnabled:false,trackingOptions:{glasses:true},camera:{},microphoneMouthWeights:{}}});
function face(gap,score){const points=Array.from({length:478},()=>({x:.5,y:.5,z:0}));for(const [a,b,c,d]of [[33,133,159,145],[362,263,386,374]]){points[a]={x:.4,y:.4};points[b]={x:.6,y:.4};points[c]={x:.5,y:.4-gap/2};points[d]={x:.5,y:.4+gap/2};}return{landmarks:points,blendshapes:[{categoryName:'eyeBlinkLeft',score},{categoryName:'eyeBlinkRight',score}],matrix:new THREE.Matrix4().identity().toArray()};}
v.owner.userTrackingSample={face:face(.05,.9),receivedAt:performance.now()};v.applyParameters();assert.equal(values.ParamEyeLOpen,1);assert.equal(values.ParamEyeROpen,1);
v.owner.userTrackingSample.face=face(.002,.2);for(let i=0;i<14;i++)v.applyParameters();assert.ok(values.ParamEyeLOpen<.01&&values.ParamEyeROpen<.01);
v.owner.userTrackingSample.face=face(.05,.9);for(let i=0;i<14;i++)v.applyParameters();assert.ok(values.ParamEyeLOpen>.99&&values.ParamEyeROpen>.99);
console.log('PASS: glasses glare rejected, real blink/weak-score closure retained, missing-landmark fallback and Live2D reopening without automatic blink');
