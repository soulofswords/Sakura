const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const THREE = require('../static/vendor/three/build/three.cjs');
const source = fs.readFileSync('static/js/model-physics.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export default class ModelPhysics','class ModelPhysics');
const ctx = vm.createContext({THREE});
vm.runInContext(source+'\nthis.Physics=ModelPhysics;',ctx);
for (const mode of ['gemini','local','vtuber']) {
 const root=new THREE.Group();
 for(const name of ['hair_1','skirt_1','breast_L','ribbon_1']) {
  const bone=new THREE.Bone();bone.name=name;bone.position.set(root.children.length,2,0);
  const end=new THREE.Bone();end.name='end';end.position.y=-1;bone.add(end);root.add(bone);
 }
 const p=new ctx.Physics();p.attach(root);p.setWindStrength(0);
 const before=p.nodes.map(n=>n.prev.clone());
 p.applyCharacterDrag(new THREE.Vector3(.4,.1,0));
 assert.ok(p.nodes.length===4 && p.nodes.every((n,i)=>n.prev.distanceTo(before[i])>.001),mode+' drag reaches all categories');
 for(let i=0;i<180;i++)p.update(1/60);
 const rest=p.nodes.map(n=>n.prev.clone());
 p.updateSpeechPhysics(1,1/60);
 assert.ok(p.nodes.some((n,i)=>n.category==='breast'&&n.prev.distanceTo(rest[i])>.0001));
 assert.ok(p.nodes.every((n,i)=>n.category==='breast'||n.prev.distanceTo(rest[i])===0),'speech only affects chest physics');
 for(let i=0;i<120;i++){p.updateSpeechPhysics(i<30?.8:0,1/60);p.update(1/60);}
 assert.ok(p.nodes.every(n=>n.bone.quaternion.toArray().every(Number.isFinite)));
 assert.ok(p._speechEnvelope<.0001,'speech force settles');
 p.setMode('off');const off=p.nodes.map(n=>n.prev.clone());
 p.applyCharacterDrag(new THREE.Vector3(1,1,1));p.updateSpeechPhysics(1,1/60);
 assert.ok(p.nodes.every((n,i)=>n.prev.distanceTo(off[i])===0),'Off remains Off');
 p.detach();assert.equal(p._speechEnvelope,0);
}
const p=new ctx.Physics(),root=new THREE.Group();
const joints=['hair','skirt','breast_L'].map(name=>{const bone=new THREE.Bone();bone.name=name;root.add(bone);return {bone,_prevTail:new THREE.Vector3()};});
p.attachVrm({scene:root,springBoneManager:{joints:new Set(joints)}});
p.applyCharacterDrag(new THREE.Vector3(.2,0,0));assert.ok(joints.every(j=>j._prevTail.length()>0));
const previous=joints.map(j=>j._prevTail.clone());p.updateSpeechPhysics(1,1/60);
assert.equal(joints[0]._prevTail.distanceTo(previous[0]),0);assert.ok(joints[2]._prevTail.distanceTo(previous[2])>0);
console.log('PASS: drag in all modes/categories, bounded speech chest response, Off, settle, detach and VRM springs');
