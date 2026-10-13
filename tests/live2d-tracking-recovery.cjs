const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),THREE=require('../static/vendor/three/build/three.cjs');
const ctx={THREE,performance};vm.runInNewContext(fs.readFileSync('static/js/live2d-viewer.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export default class Live2DViewer','class Live2DViewer')+'\nthis.Live=Live2DViewer;',ctx);
const values={},live=Object.create(ctx.Live.prototype);Object.assign(live,{filtered:{},values:{},neutral:null,eyeNeutral:{},owner:{userTracking:true,vtuberTrackingMode:true},avatar:{internalModel:{coreModel:{getParameterIndex(){return 0;},setParameterValueById(id,value){values[id]=value;}}}}});
const frame=face=>{live.owner.userTrackingSample={face,receivedAt:performance.now()};assert.doesNotThrow(()=>live.applyParameters());assert.ok(Object.values(values).every(Number.isFinite),'Missing face cannot write NaN');};
frame({landmarks:[],matrix:null,blendshapes:[]});assert.equal(live.neutral,null);assert.equal(values.ParamAngleX,0);
frame({landmarks:[{}],matrix:null,blendshapes:[{categoryName:'jawOpen',score:.5}]});assert.equal(live.neutral,null);assert.ok(values.ParamMouthOpenY>0,'Mouth can track before the head matrix arrives');
frame({landmarks:[{}],matrix:Array(16).fill(NaN),blendshapes:[]});assert.equal(live.neutral,null);
frame({landmarks:[{}],matrix:new THREE.Matrix4().identity().toArray(),blendshapes:[]});assert.ok(live.neutral,'First real pose calibrates');
for(let i=0;i<30;i++)frame({landmarks:[{}],matrix:new THREE.Matrix4().makeRotationY(.2).toArray(),blendshapes:[]});assert.ok(values.ParamAngleX>10,'Head resumes after pose reacquisition');
live.neutral=null;frame({landmarks:[],matrix:null,blendshapes:[]});frame({landmarks:[{}],matrix:new THREE.Matrix4().identity().toArray(),blendshapes:[]});
console.log('PASS: new Live2D tracking with missing face/matrix, invalid pose, mouth-only frame, reacquisition and model-switch recalibration');
function response(fps){
    live.filtered={};live.neutral=new THREE.Euler();live.renderDelta=1/fps;
    frame({landmarks:[{}],matrix:new THREE.Matrix4().identity().toArray(),blendshapes:[]});
    for(let i=0;i<fps/10;i++)frame({landmarks:[{}],matrix:new THREE.Matrix4().makeRotationY(.2).toArray(),blendshapes:[{categoryName:'jawOpen',score:1}]});
    return {head:values.ParamAngleX,mouth:values.ParamMouthOpenY};
}
const slow=response(30),fast=response(60);assert.ok(Math.abs(slow.head-fast.head)<1e-6,'Smoothing must have the same response at 30 and 60 FPS');assert.ok(Math.abs(slow.mouth-fast.mouth)<1e-6);assert.ok(slow.mouth>.99,'Mouth responds within 100ms');
console.log('PASS: time-based Live2D smoothing at 30/60 FPS and responsive mouth');
const source=fs.readFileSync('static/js/live2d-viewer.js','utf8');
assert.match(source,/on\('afterMotionUpdate',\(\)=>v.applyParameters\(\)\)/,'Tracking inputs reach authored physics before visible model evaluation');
assert.doesNotMatch(source,/on\('beforeModelUpdate',\(\)=>v.applyParameters\(\)\)/,'Tracking must not be written after the physics routing stage');
