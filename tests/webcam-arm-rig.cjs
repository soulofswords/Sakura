const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const THREE=require('../static/vendor/three/build/three.cjs');
const context=vm.createContext({console,TextDecoder});
vm.runInContext(fs.readFileSync('static/vendor/three/examples/jsm/libs/mmdparser.module.js','utf8').replace('export { MMDParser, CharsetEncoder, Parser };','globalThis.Parser=Parser;'),context);
const bytes=fs.readFileSync('models/pmx/arknights endfield/Chen Qianyu/Chen Qianyu.pmx');
const data=new context.Parser().parsePmx(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),true);
const source=fs.readFileSync('static/js/avatar-retarget.js','utf8').replace(/import \* as THREE from 'three';/,'')
    .replace(/export function /g,'function ').replace('export default class AvatarRetarget','class AvatarRetarget');
const Retarget=new Function('THREE',source+';return AvatarRetarget;')(THREE);
const root=new THREE.Group(),bones=data.bones.map(entry=>{const bone=new THREE.Bone();bone.name=entry.name;return bone;});
data.bones.forEach((entry,i)=>{const parent=entry.parentIndex;(parent>=0?bones[parent]:root).add(bones[i]);bones[i].position.fromArray(entry.position);if(parent>=0)bones[i].position.sub(new THREE.Vector3().fromArray(data.bones[parent].position));});
const entries={};
for(const [side,prefix] of [['left','左'],['right','右']])for(const [key,suffix] of [['Shoulder','肩'],['Arm','腕'],['Elbow','ひじ'],['Wrist','手首']]){const bone=bones.find(b=>b.name===prefix+suffix);assert(bone);entries[side+key]={bone,rest:bone.rotation.clone()};}
const viewer={model:root,animationBones:entries,morphMap:{},setMorph(){}};
const rig=new Retarget(viewer);root.updateMatrixWorld(true);
assert.equal(rig.fingers.length,30,'all thirty PMX finger joints are mapped');
assert(rig.fingers.every(f=>f.bendAxis.lengthSq()>.99),'each finger joint has a normalized rig-derived bending axis');
assert(rig.fingers.some(f=>Math.abs(f.bendAxis.z)<.99),'finger axes must follow the angled hand rig rather than a universal Z axis');
for(const side of ['left','right']) {
    const wrist=entries[side+'Wrist'].bone;
    const initial=wrist.getWorldPosition(new THREE.Vector3());
    const target=initial.clone().add(new THREE.Vector3(side==='left'?-2:2,3,3));
    viewer.trackingOptions={handRange:1};rig.handTargets={};rig.solveArm(side,target,.25);
    const anchor=entries[side+'Shoulder'].bone.getWorldPosition(new THREE.Vector3());
    const normalDistance=rig.handTargets[side].distanceTo(anchor);
    viewer.trackingOptions={handRange:1.8};rig.handTargets={};rig.solveArm(side,target,.25);
    assert(Math.abs(rig.handTargets[side].distanceTo(anchor)/normalDistance-1.8)<1e-5,'hand range scales distance independently of head tracking');
    viewer.trackingOptions={handRange:1.3};rig.handTargets={};
    for(let i=0;i<300;i++)rig.solveArm(side,target,.25);
    root.updateMatrixWorld(true);const position=wrist.getWorldPosition(new THREE.Vector3());
    assert(position.z>initial.z+1,'Chen Qianyu reaches forward, not behind the torso');
    const settled=wrist.quaternion.clone();
    for(let i=0;i<300;i++)rig.solveArm(side,target,.25);
    assert(wrist.quaternion.angleTo(settled)<1e-5,'real PMX rig does not accumulate wrist/arm rotation');
    assert(Object.values(entries).every(e=>e.bone.quaternion.toArray().every(Number.isFinite)));
}
console.log('PASS: real Chen Qianyu PMX arm chains reach forward on both sides and remain stable under repeated stationary targets');
