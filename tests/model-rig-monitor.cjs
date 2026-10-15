const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const THREE=require('../static/vendor/three/build/three.cjs');let now=0;const saved=new Map();
const context={performance:{now:()=>now},localStorage:{getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v),removeItem:k=>saved.delete(k)},window:{dispatchEvent(){}},CustomEvent:class{},console,Date};
vm.runInNewContext(fs.readFileSync('static/js/model-rig-monitor.js','utf8').replace('export default class ModelRigMonitor','class ModelRigMonitor')+'\nthis.Monitor=ModelRigMonitor;',context);
const bone=new THREE.Bone();bone.name='hair';const node={index:7,bone,restLocal:new THREE.Vector3(),restQuat:new THREE.Quaternion()};
const viewer={physics:{nodes:[node],mode:'normal'},captureSpoutFrame(){return null;},loadGeneration:1};const monitor=new context.Monitor(viewer);
monitor.sample(1000);assert.equal(viewer.rigAnalysis,undefined,'Placeholder frames must not diagnose an unloaded rig');
monitor.start('/models/test.pmx');for(let i=0;i<81;i++){now=i*100;monitor.sample(now);}assert.equal(viewer.rigAnalysis.frozen.length,0,'Valid hair never frozen');
monitor.start('/models/test.pmx');for(let i=1;i<82;i++){now+=100;bone.position.set(5,0,0);monitor.sample(now);}assert.deepEqual(Array.from(viewer.rigAnalysis.frozen),[7]);assert.ok(!node.diagnosticStatic,'First load reports only');
bone.position.set(0,0,0);monitor.start('/models/test.pmx');assert.equal(node.diagnosticStatic,true,'Next load freezes only identified node');
monitor.reset();assert.equal(node.diagnosticStatic,false,'Reset restores physics');
// A changed rig must not inherit a prior model's frozen indices.
saved.set(monitor.key(),JSON.stringify({signature:'old rig',frozen:[7]}));monitor.start('/models/test.pmx');assert.equal(node.diagnosticStatic,false);
const physicsContext={THREE,console};vm.runInNewContext(fs.readFileSync('static/js/model-physics.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export default class ModelPhysics','class ModelPhysics')+'\nthis.Physics=ModelPhysics;',physicsContext);
const physics=new physicsContext.Physics(),root=new THREE.Group();root.add(bone);Object.assign(node,{diagnosticStatic:true,tailLocal:new THREE.Vector3(0,1,0),pos:new THREE.Vector3(9,9,9),prev:new THREE.Vector3(8,8,8)});physics.model=root;physics.nodes=[node];bone.position.set(5,0,0);bone.rotation.z=2;root.updateMatrixWorld(true);physics._step({gravity:1,stiffness:1,drag:0,wind:0},1/60);assert.equal(bone.position.length(),0);assert.ok(bone.quaternion.angleTo(node.restQuat)<1e-6);assert.equal(node.pos.distanceTo(node.prev),0);
console.log('PASS: normal rig retained, sustained bad bone saved, selective next-load freeze, reset, edited-rig invalidation and solver rest pose');
// Model-only snapshots are captured at two and eight seconds, not each frame.
let captures=0,imageWrites=0;
context.ImageData=class{};context.document={createElement(){return {getContext(){return {putImageData(){}};},toBlob(callback){callback({capture:captures});}};}};
viewer.captureSpoutFrame=()=>{captures++;return {width:1,height:1,pixels:new Uint8Array(4)};};monitor.storeImage=(blob,report)=>{imageWrites++;assert.equal(report.version,2);};
bone.position.set(0,0,0);bone.quaternion.identity();node.params={maxAngle:50};monitor.start('/models/limits.pmx?cache=first');
for(let i=1;i<82;i++){now+=100;bone.rotation.z=70*Math.PI/180;monitor.sample(now);}
assert.deepEqual(Array.from(viewer.rigAnalysis.frozen),[7],'Sustained authored-limit violation is detected');assert.equal(captures,2);assert.equal(imageWrites,1);assert.ok(viewer.rigDiagnosticReference&&viewer.rigDiagnosticImage);assert.equal(node.diagnosticStatic,false);
monitor.start('/models/limits.pmx?cache=second');assert.equal(node.diagnosticStatic,true,'Cache busting cannot lose automatic freeze');
monitor.unfreezeBone(bone);assert.equal(node.diagnosticStatic,false,'User can restore diagnosed bone');assert.equal(viewer.diagnosticFrozenBones.size,0);
// Brief legitimate movements are retained even when temporarily past a limit.
monitor.reset();for(let i=1;i<82;i++){now+=100;bone.rotation.z=i<15?70*Math.PI/180:0;monitor.sample(now);}assert.equal(viewer.rigAnalysis.frozen.length,0);
// VRM native spring joints use the same diagnosis and next-load parking.
const vrmBone=new THREE.Bone();vrmBone.name='HairVRM';const vrmViewer={vrm:{},physics:{nodes:[],vrmPhysicsJoints:[{bone:vrmBone}],mode:'normal'},captureSpoutFrame(){return null;},loadGeneration:1};
const vrmMonitor=new context.Monitor(vrmViewer);vrmMonitor.start('/models/test.vrm');for(let i=1;i<82;i++){now+=100;vrmBone.position.set(8,0,0);vrmMonitor.sample(now);}assert.deepEqual(Array.from(vrmViewer.rigAnalysis.frozen),[0]);
vrmBone.position.set(0,0,0);vrmMonitor.start('/models/test.vrm');vrmBone.position.set(8,0,0);vrmMonitor.enforce();assert.equal(vrmBone.position.length(),0);
console.log('PASS: timed screenshots, sustained rotation limits, brief normal movement, stable keys, manual restoration and VRM next-load freeze');
// Rechecking a posed VRM must retain the original bind/rest signature.
const originalVrmSignature=vrmMonitor.signature;
vrmBone.position.set(4,0,0);vrmBone.rotation.z=.7;vrmMonitor.start('/models/test.vrm');
assert.equal(vrmMonitor.signature,originalVrmSignature,'Current tracking/physics pose cannot change the saved VRM rig identity');
vrmMonitor.applyFrozen();assert.equal(vrmBone.position.length(),0);
// User-triggered screenshots begin a fresh check without requiring a reload.
bone.quaternion.identity();bone.position.copy(node.restLocal);monitor.start('/models/button.pmx');
viewer.model=root;const before=captures;assert.equal(monitor.checkNow(),true);assert.equal(captures,before+1,'Button captures the model immediately');
for(let i=1;i<82;i++){now+=100;node.collisionConflict=true;monitor.sample(now);}
assert.deepEqual(Array.from(viewer.rigAnalysis.frozen),[7],'Sustained collider conflict is diagnosed despite safely clamped bone rotation');
