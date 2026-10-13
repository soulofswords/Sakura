const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const THREE=require('../static/vendor/three/build/three.cjs');
const src=fs.readFileSync('static/js/model-physics.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export default class ModelPhysics','class ModelPhysics');
const ctx=vm.createContext({THREE});vm.runInContext(src+'\nthis.Physics=ModelPhysics;',ctx);
for(const shape of [0,1,2]) {
 const p=new ctx.Physics();p.hairColliders=[{shape,world:new THREE.Matrix4(),inverse:new THREE.Matrix4(),center:new THREE.Vector3(),boundRadius:1,radius:.5,height:1,size:new THREE.Vector3(.5,.5,.5)}];
 const anchor=new THREE.Vector3(0,2,0),rest=new THREE.Vector3(2,0,0),node={pos:new THREE.Vector3(0,.1,0),prev:new THREE.Vector3(0,.1,0)};
 p._collideHair(node,anchor,rest,2);
 assert.ok(node.pos.toArray().every(Number.isFinite));
 assert.ok(node.pos.distanceTo(new THREE.Vector3(0,.1,0))>.1,'collision pushes penetrating hair for shape '+shape);
 assert.ok(Math.abs(node.pos.distanceTo(anchor)-2)<1e-6,'strand keeps its length');
}
// A model can ship a strand whose middle rest pose overlaps a shoulder or
// garment collider. Only the scalp attachment may bypass that overlap; lower
// strand points still need collision correction.
{
 const p=new ctx.Physics();p.hairColliders=[{shape:0,world:new THREE.Matrix4(),inverse:new THREE.Matrix4(),center:new THREE.Vector3(),boundRadius:.5,radius:.5,height:1,size:new THREE.Vector3(.5,.5,.5)}];
 const anchor=new THREE.Vector3(0,2,0),rest=new THREE.Vector3(0,-2,0),node={pos:new THREE.Vector3(0,-2,0),prev:new THREE.Vector3(0,-2,0)};
 p._collideHair(node,anchor,rest,4);
 assert.ok(node.pos.distanceTo(new THREE.Vector3(0,-2,0))>.1,'lower strand is corrected even when its authored rest path intersects the body');
 assert.ok(Math.abs(node.pos.distanceTo(anchor)-4)<1e-6,'rest-pose collision correction preserves strand length');
}
const p=new ctx.Physics(),root=new THREE.Group(),b=new THREE.Bone();b.name='breast_L';b.position.set(1,12,2);root.add(b);p.attach(root);
assert.ok(p.nodes[0].tailLocal.length()<.5,'chest leaf uses short local lever');
const prev=p.nodes[0].prev.clone();p.applyCharacterDrag(new THREE.Vector3(.4,0,0));assert.ok(p.nodes[0].prev.distanceTo(prev)>.02);
console.log('PASS: sphere, box and capsule hair collisions; finite bounded strands; short chest lever and drag response');
