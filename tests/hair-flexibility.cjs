const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const THREE = require('../static/vendor/three/build/three.cjs');
const context = vm.createContext({THREE, console, TextDecoder});
vm.runInContext(fs.readFileSync('static/vendor/three/examples/jsm/libs/mmdparser.module.js','utf8')
    .replace('export { MMDParser, CharsetEncoder, Parser };','globalThis.Parser=Parser;'), context);
vm.runInContext(fs.readFileSync('static/js/model-physics.js','utf8').replace(/^import .*;\r?\n/gm,'')
    .replace('export default class ModelPhysics','class ModelPhysics')+'\nthis.Physics=ModelPhysics;', context);
function makeRig(data, uniform) {
    const mesh = new THREE.SkinnedMesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial());
    const bones = data.bones.map(entry => {const bone = new THREE.Bone();bone.name=entry.name;return bone;});
    data.bones.forEach((entry,i) => {
        const parent = entry.parentIndex;
        (parent >= 0 ? bones[parent] : mesh).add(bones[i]);
        bones[i].position.fromArray(entry.position);
        if (parent >= 0) bones[i].position.sub(new THREE.Vector3().fromArray(data.bones[parent].position));
    });
    mesh.bind(new THREE.Skeleton(bones));
    const types = new Map(data.rigidBodies.map(body => [body.boneIndex, body.type]));
    mesh.geometry.userData.MMD = {bones:data.bones.map((entry,i) => ({name:entry.name,parent:entry.parentIndex,rigidBodyType:types.get(i)}))};
    const physics = new context.Physics();physics.attach(mesh);physics.setWindStrength(0);
    if (uniform) for (const node of physics.nodes) if (node.category === 'hair') node.params={...node.params,stiffness:.22};
    return {mesh,bones,physics};
}
const folder=path.join('models','pmx','arknights endfield','Yvonne');
const file=fs.readdirSync(folder).find(name=>/\.pmx$/i.test(name));
const bytes=fs.readFileSync(path.join(folder,file));
const data=new context.Parser().parsePmx(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),true);
const old=makeRig(data,true), flexible=makeRig(data,false);
const strand=flexible.physics.nodes.filter(node=>/hair_mawei_L_a__jnt/i.test(node.bone.name));
assert.equal(strand.length,10);
assert.equal(strand[0].params.stiffness,.22,'root stiffness stays unchanged');
assert(strand[4].params.stiffness < strand[0].params.stiffness*.5,'middle of long hair bends more easily');
let oldMotion=0,newMotion=0;
const sampleName='hair_mawei_L_a__jnt6';
for(let frame=0;frame<900;frame++) {
    for(const rig of [old,flexible]) {
        rig.mesh.rotation.z=frame<300 ? Math.sin(frame/15)*.18 : 0;
        rig.physics.update(1/60);
        for(const node of rig.physics.nodes) {
            assert(node.pos.toArray().every(Number.isFinite),'particles must remain finite');
            assert(node.bone.quaternion.toArray().every(Number.isFinite),'bone rotations must remain finite');
            assert(Math.abs(node.bone.quaternion.length()-1)<1e-5);
        }
    }
    if(frame<300) {
        const node=rig=>rig.physics.nodes.find(n=>n.bone.name===sampleName);
        oldMotion+=node(old).bone.quaternion.angleTo(node(old).restQuat);
        newMotion+=node(flexible).bone.quaternion.angleTo(node(flexible).restQuat);
    }
}
assert(newMotion > oldMotion*1.05,'middle hair must respond more freely to character movement');
flexible.physics.setMode('off');
for(const node of flexible.physics.nodes) assert(node.bone.quaternion.angleTo(node.restQuat)<1e-6);
console.log(`PASS: Yvonne's 10-segment hair chain has softer middle bends, firm roots, stable movement/settling and Off reset (${(newMotion/oldMotion).toFixed(2)}x middle response)`);
