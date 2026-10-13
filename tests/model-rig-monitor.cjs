const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const THREE=require('../static/vendor/three/build/three.cjs');let now=0;const saved=new Map();
const context={performance:{now:()=>now},localStorage:{getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v),removeItem:k=>saved.delete(k)},window:{dispatchEvent(){}},CustomEvent:class{},console,Date};
vm.runInNewContext(fs.readFileSync('static/js/model-rig-monitor.js','utf8').replace('export default class ModelRigMonitor','class ModelRigMonitor')+'\nthis.Monitor=ModelRigMonitor;',context);
const bone=new THREE.Bone();bone.name='hair';const node={index:7,bone,restLocal:new THREE.Vector3(),restQuat:new THREE.Quaternion()};
const viewer={physics:{nodes:[node],mode:'normal'},captureSpoutFrame(){return null;},loadGeneration:1};const monitor=new context.Monitor(viewer);
monitor.start('/models/test.pmx');for(let i=0;i<81;i++){now=i*100;monitor.sample(now);}assert.equal(viewer.rigAnalysis.frozen.length,0,'Valid hair never frozen');
monitor.start('/models/test.pmx');for(let i=1;i<82;i++){now+=100;bone.position.set(5,0,0);monitor.sample(now);}assert.deepEqual(Array.from(viewer.rigAnalysis.frozen),[7]);assert.ok(!node.diagnosticStatic,'First load reports only');
bone.position.set(0,0,0);monitor.start('/models/test.pmx');assert.equal(node.diagnosticStatic,true,'Next load freezes only identified node');
monitor.reset();assert.equal(node.diagnosticStatic,false,'Reset restores physics');
// A changed rig must not inherit a prior model's frozen indices.
saved.set(monitor.key(),JSON.stringify({signature:'old rig',frozen:[7]}));monitor.start('/models/test.pmx');assert.equal(node.diagnosticStatic,false);
const physicsContext={THREE,console};vm.runInNewContext(fs.readFileSync('static/js/model-physics.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export default class ModelPhysics','class ModelPhysics')+'\nthis.Physics=ModelPhysics;',physicsContext);
const physics=new physicsContext.Physics(),root=new THREE.Group();root.add(bone);Object.assign(node,{diagnosticStatic:true,tailLocal:new THREE.Vector3(0,1,0),pos:new THREE.Vector3(9,9,9),prev:new THREE.Vector3(8,8,8)});physics.model=root;physics.nodes=[node];bone.position.set(5,0,0);bone.rotation.z=2;root.updateMatrixWorld(true);physics._step({gravity:1,stiffness:1,drag:0,wind:0},1/60);assert.equal(bone.position.length(),0);assert.ok(bone.quaternion.angleTo(node.restQuat)<1e-6);assert.equal(node.pos.distanceTo(node.prev),0);
console.log('PASS: normal rig retained, sustained bad bone saved, selective next-load freeze, reset, edited-rig invalidation and solver rest pose');
