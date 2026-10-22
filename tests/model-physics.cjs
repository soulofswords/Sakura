const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const THREE = require('../static/vendor/three/build/three.cjs');
const source = fs.readFileSync('static/js/model-physics.js', 'utf8')
    .replace(/^import .*;\r?\n/gm, '').replace('export default class ModelPhysics', 'class ModelPhysics');
const context = vm.createContext({ THREE });
vm.runInContext(source + '\nthis.ModelPhysics = ModelPhysics;', context);
const Physics = context.ModelPhysics;
function rig(scale = 1) {
    const model = new THREE.Group();
    model.scale.setScalar(scale);
    model.rotation.z = .2;
    const hinge = new THREE.Bone(); hinge.name = 'hair'; hinge.position.set(0, 2, 0);
    const tail = new THREE.Bone(); tail.name = 'end'; tail.position.set(1, 0, 0);
    model.add(hinge); hinge.add(tail);
    const physics = new Physics(); physics.attach(model);
    assert.equal(physics.info.bones, 1);
    return { model, hinge, tail, physics };
}
for (const scale of [1, 2]) {
    const r = rig(scale);
    const origin = r.hinge.getWorldPosition(new THREE.Vector3());
    for (let i = 0; i < 180; i++) r.physics.update(1 / 60);
    r.model.updateMatrixWorld(true);
    assert.ok(r.tail.getWorldPosition(new THREE.Vector3()).distanceTo(r.physics.nodes[0].pos) < 1e-6,
        'Simulated particle matches actual tail after rotation');
    assert.ok(r.hinge.getWorldPosition(new THREE.Vector3()).distanceTo(origin) < 1e-6,
        'Rotation keeps its own origin fixed');
    r.physics.setMode('off');
    assert.ok(r.hinge.quaternion.angleTo(new THREE.Quaternion()) < 1e-6);
}
const a = rig(), b = rig();
for (let i = 0; i < 120; i++) a.physics.update(1 / 60);
for (let i = 0; i < 60; i++) b.physics.update(1 / 30);
assert.ok(a.physics.nodes[0].pos.distanceTo(b.physics.nodes[0].pos) < 1e-9);
let steps = 0;
a.physics._step = () => steps++;
a.physics.update(1);
assert.equal(steps, 4); assert.equal(a.physics._accumulator, 0);
const joints = new Set([{}, {}]);
assert.equal(new Physics().attachVrm({scene: new THREE.Group(), springBoneManager:{joints}}).bones, 2);
const root = new THREE.Group(); let last = root;
for (let i = 0; i < 140; i++) { const bone = new THREE.Bone(); bone.position.x = 1; last.add(bone); last = bone; }
root.updateMatrixWorld(true);
assert.ok(new THREE.Vector3().setFromMatrixPosition(b.physics._parentWorld(last)).distanceTo(new THREE.Vector3(140,0,0)) < 1e-8);
const viewerSource = fs.readFileSync('static/js/model-viewer.js', 'utf8').replace(/\r\n/g, '\n');
const reattach = new Function('enabled', viewerSource.match(/setGlitchFix\(enabled\) \{([\s\S]*?)\n    \}\n\n    repairPhysics/)[1]);
const repairPhysics = new Function(viewerSource.match(/repairPhysics\(\) \{([\s\S]*?)\n    \}\n\n    setPhysicsStrength/)[1]);
for (const mode of ['gemini', 'local', 'vtuber']) {
    const physics = new Physics();
    const model = new THREE.Group();
    const hair = new THREE.Bone(); hair.name = 'hair'; model.add(hair);
    physics.attach(model);
    physics.setStrength(1.2); physics.setWindStrength(.4);
    hair.quaternion.setFromAxisAngle(new THREE.Vector3(0,0,1), .8);
    const activeViewer = {model, physics, animationBones:{}, userTracking:mode === 'vtuber', vrm:null, setGlitchFix:reattach};
    const info = repairPhysics.call(activeViewer);
    assert.equal(info.engine, 'spring-chain', `${mode} repair must use safe springs`);
    assert.equal(info.bones, 1);
    assert.ok(hair.quaternion.angleTo(new THREE.Quaternion()) < 1e-6, `${mode} repair restores physics rest pose`);
    assert.equal(physics.strength, 1.2);
    assert.equal(physics.windStrength, .4);
    assert.equal(activeViewer.userTracking, mode === 'vtuber', 'repair must preserve tracking state');
}
console.log('PASS: manual physics repair resets PMX bones in Gemini, Local LLM and active VTuber tracking, preserving sliders');
const sync = new Function(viewerSource.match(/_syncVrmPhysics\(\) \{([\s\S]*?)\n    \}\n\n    setEmotionFromText/)[1]);
let resets = 0;
const joint = { settings: { stiffness: 2, gravityPower: .7, dragForce: .9 } };
const viewer = { physics: { mode: 'normal' }, vrm: { springBoneManager: { joints: new Set([joint]), reset(){resets++;} } } };
for (const mode of ['subtle', 'lively', 'off', 'normal', 'subtle', 'normal']) {
    viewer.physics.mode = mode; sync.call(viewer);
    assert.ok(joint.settings.dragForce >= 0 && joint.settings.dragForce <= 1);
}
assert.equal(resets, 1);
assert.deepEqual(joint.settings, { stiffness: 2, gravityPower: .7, dragForce: .9 });
console.log('PASS: tail pivot, scaled rigs, fixed-step equivalence, stall cap, deep matrices, VRM Sets, Off reset and exact Normal restoration');

function authoredRig(count, broken = false) {
    const mesh = new THREE.SkinnedMesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial());
    const bones = Array.from({length: count}, (_, i) => {
        const bone = new THREE.Bone(); bone.name = i === 0 ? 'hair' : `dynamic_${i}`;
        bone.position.set(0, 1, 0); mesh.add(bone); return bone;
    });
    mesh.bind(new THREE.Skeleton(bones));
    mesh.geometry.userData.MMD = {bones: bones.map((bone, i) => ({name: bone.name, parent: broken && i === 0 ? 0 : -1, rigidBodyType: 1}))};
    return mesh;
}
const large = new Physics(); large.attach(authoredRig(521));
assert.equal(large.info.source, 'model rig');
assert.equal(large.info.bones, 521, 'Every dynamic rig bone is retained, including accessories without recognized names');
large.update(1/60);
const fitted=authoredRig(2),shape=new THREE.Bone();shape.name='LeftBreastAdjustment';shape.position.set(.1,0,0);
fitted.add(shape);fitted.bind(new THREE.Skeleton([...fitted.skeleton.bones,shape]));
fitted.geometry.userData.MMD.bones.push({name:shape.name,parent:-1,rigidBodyType:0});
const fittedPhysics=new Physics();fittedPhysics.attach(fitted);
assert.equal(fittedPhysics.nodes.length,2,'Authored dynamics must not acquire extra name-matched chest shape springs');
assert.ok(!fittedPhysics.nodes.some(n=>n.bone===shape));
for(let i=0;i<240;i++)fittedPhysics.update(1/60);
assert.ok(shape.quaternion.angleTo(new THREE.Quaternion())<1e-6,'Fitted top adjustment bone retains its authored pose');
const malformed = new Physics(); malformed.attach(authoredRig(3, true));
assert.equal(malformed.info.source, 'name match'); assert.equal(malformed.info.bones, 1);
context.validBulletRig = () => true;
const safeRig = new Physics();
safeRig.requireBullet = true; safeRig.bulletReady = true;
const safeInfo = safeRig.attach(authoredRig(3));
assert.equal(safeInfo.engine, 'spring-chain', 'all PMX rigs start on safe springs by default');
assert.equal(safeInfo.bones, 3, 'the safe solver includes every dynamic PMX bone');
assert.match(safeInfo.warning, /Safe spring-chain physics is active for PMX rigs/);
assert.equal(safeRig.bullet, null);
assert.match(viewerSource, /this\.physics\.forceSpring = !isVrm && options\.forceSpring !== false/,
    'file uploads and model-directory loads share the safe PMX default');
context.validBulletRig = () => false;
const invalidBulletRig = new Physics();
const invalidBulletInfo = invalidBulletRig.attach(authoredRig(3));
assert.equal(invalidBulletInfo.engine, 'spring-chain');
assert.equal(invalidBulletInfo.source, 'model rig');
assert.equal(invalidBulletInfo.bones, 3, 'PMX dynamic bones remain simulated even when the Bullet-specific rig check fails');
const brokenBullet = new Physics(); brokenBullet.requireBullet = true;
brokenBullet.attach(authoredRig(3));
assert.equal(brokenBullet.info.source, 'model rig');
assert.equal(brokenBullet.info.bones, 3);
function repeatedNameRig() {
    const mesh = new THREE.SkinnedMesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial());
    const anchor = new THREE.Bone(); anchor.name = 'root'; anchor.position.set(0, 1, 0); mesh.add(anchor);
    const entries = [{name:'root',parent:-1,rigidBodyType:0}];
    const bones = [anchor];
    for (const [name, x, y] of [['スカート_0_1',1,0],['スカート_0_1',-1,0],['スカート_0_1',0,1],['スカート_0_1',0,1]]) {
        const bone = new THREE.Bone(); bone.name=name; bone.position.set(x,y,0); anchor.add(bone);
        bones.push(bone); entries.push({name,parent:0,rigidBodyType:1});
    }
    mesh.bind(new THREE.Skeleton(bones)); mesh.geometry.userData.MMD={bones:entries};
    return {mesh,bones};
}
const repeated = new Physics();
repeated.glitchFixEnabled=true;
const repeatedRig = repeatedNameRig();
const glitchInfo = repeated.attach(repeatedRig.mesh);
assert.equal(glitchInfo.bones,3,'Same-name skirt panels with distinct pivots must remain simulated');
assert.equal(glitchInfo.glitch.detected,1,'Only the coincident duplicate pivot is a cleanup candidate');
assert.equal(glitchInfo.glitch.active,true);
assert.equal(glitchInfo.glitch.removed,1);
assert.equal(glitchInfo.glitch.groups[0].name,'スカート_0_1');
const autoCleanup = new Physics();
const autoInfo = autoCleanup.attach(repeatedRig.mesh);
assert.equal(autoInfo.bones,3,'New PMX rigs automatically exclude structural duplicate pivots on attach');
assert.equal(autoInfo.glitch.active,true,'Automatic cleanup is visible immediately after model load');
const repeatRestore = new Physics();repeatRestore.glitchFixPolicy='off';repeatRestore.attach(repeatedRig.mesh);
assert.equal(repeatRestore.info.bones,4,'Opting out restores simulation without mutating or deleting source bones');
const coincidentDifferentName = new Physics();
coincidentDifferentName._rigContext={mesh:repeatedRig.mesh,mmdBones:repeatedRig.mesh.geometry.userData.MMD.bones.map((entry,i)=>i===4?{...entry,name:'different-name'}:entry)};
assert.equal(coincidentDifferentName.detectGlitchBones().detected,0,'A valid zero-offset or coincident pivot with a different name is not removed');
const fallbackCleanup = new Physics();fallbackCleanup.requireBullet=true;fallbackCleanup.glitchFixEnabled=true;
fallbackCleanup.attach(repeatedRig.mesh);
assert.equal(fallbackCleanup.info.source,'model rig');
assert.equal(fallbackCleanup.info.bones,3,'Safe spring solver must honor the cleanup exclusion');
assert.equal(fallbackCleanup.info.glitch.detected,1);
console.log('PASS: PMX cleanup preserves legitimate duplicate-name chains, automatically excludes only coincident pivots, restores originals and applies to fallback');
const multilingual = new THREE.Group();
for (const name of ['髪', 'スカート', '胸', 'リボン', '尻尾', '袖', '头发', '裙', '丝带', '尾巴', '衣袖', '配饰', 'hair', 'skirt', 'breast', 'ribbon', 'tail', 'sleeve', 'accessory']) {
    const bone = new THREE.Bone(); bone.name = name; multilingual.add(bone);
}
const fallback = new Physics(); fallback.attach(multilingual);
assert.equal(fallback.info.bones, multilingual.children.length);
const noPhysics = new Physics();
const plain = new THREE.Group(); const head = new THREE.Bone(); head.name = 'head'; plain.add(head);
assert.equal(noPhysics.attach(plain).bones, 0);
const reserved = new Physics(); reserved.attach(multilingual, new Set(['胸']));
assert.equal(reserved.info.bones, multilingual.children.length - 1);
const validate = new Function('data', viewerSource.match(/_validatePmxReferences\(data\) \{([\s\S]*?)\n    \}\n\n    _preparePmxMorphData/)[1]);
const invalidData = {metadata:{format:'pmx',rigidBodyCount:1,constraintCount:1}, morphs:[],bones:[{}],materials:[],
    rigidBodies:[{boneIndex:9,type:1}],constraints:[{rigidBodyIndex1:0,rigidBodyIndex2:12}]};
const repaired = validate(invalidData);
assert.equal(repaired.rigidBodies.length, 0); assert.equal(repaired.constraints.length, 0);
assert.equal(invalidData.rigidBodies.length, 1, 'Source data is preserved');
const app = fs.readFileSync('static/js/app.js', 'utf8').replace(/\r\n/g, '\n');
const ui = new Function('viewer', 'document', 'mode', app.match(/function updatePhysicsUI\(mode\) \{([\s\S]*?)\n\}\n\nfunction setTransparency/)[1]);
const status = {};
const doc = {querySelectorAll(){return []},getElementById(){return status}};
ui({physics:noPhysics, physicsInfo:noPhysics.info},doc,'normal');
assert.ok(status.textContent.includes('No physics available'));
ui({physics:large, physicsInfo:large.info},doc,'normal');
assert.ok(status.textContent.includes('521 bones') && status.textContent.includes('Normal'));
large.setMode('off'); ui({physics:large, physicsInfo:large.info},doc,'off');
assert.ok(status.textContent.includes('521 bones') && status.textContent.includes('Off'));
console.log('PASS: automatic rig detection, all dynamic bones, invalid rig fallback, multilingual names, reserved bones, no-physics status and mode/count display');

const adjustable = rig();
assert.equal(adjustable.physics.setStrength(NaN), false);
assert.equal(adjustable.physics.setWindStrength(Infinity), false);
adjustable.physics.setStrength(9); assert.equal(adjustable.physics.strength, 1.5);
adjustable.physics.setWindStrength(9); assert.equal(adjustable.physics.windStrength, 1);
adjustable.physics.setStrength(0);
assert.equal(adjustable.physics.mode, 'off');
assert.ok(adjustable.hinge.quaternion.angleTo(new THREE.Quaternion()) < 1e-6);
adjustable.physics.setStrength(.75); adjustable.physics.update(1/60);
assert.equal(adjustable.physics.mode, 'custom');
assert.ok(adjustable.physics.nodes[0].pos.toArray().every(Number.isFinite));
const windJoint = {settings:{stiffness:2,gravityPower:.7,dragForce:.9,gravityDir:new THREE.Vector3(0,-1,0)}};
const windViewer = {physics:{mode:'custom',strength:1,windStrength:1},vrm:{springBoneManager:{joints:new Set([windJoint]),reset(){}}}};
sync.call(windViewer);
assert.ok(windJoint.settings.gravityDir.x > 0);
assert.ok(Math.abs(windJoint.settings.gravityDir.length()-1) < 1e-9);
windViewer.physics.strength=.5; sync.call(windViewer);
assert.equal(windJoint.settings.stiffness,1);
windViewer.physics.mode='off'; sync.call(windViewer);
assert.equal(windJoint.settings.gravityPower,0);
windViewer.physics.mode='custom'; windViewer.physics.strength=1; windViewer.physics.windStrength=0; sync.call(windViewer);
assert.equal(windJoint.settings.stiffness,2); assert.equal(windJoint.settings.gravityPower,.7);
assert.equal(windJoint.settings.dragForce,.9); assert.deepEqual(windJoint.settings.gravityDir.toArray(),[0,-1,0]);
console.log('PASS: continuous strength bounds, Off/resume, wind bounds, VRM wind direction and exact restoration');

const drag = rig(), hairNode=drag.physics.nodes[0];
const clothNode={category:'skirt',prev:new THREE.Vector3(0,2,0)};
drag.physics.nodes.push(clothNode);
const hairBefore=hairNode.prev.clone(),clothBefore=clothNode.prev.clone();
drag.physics.applyHairDrag(new THREE.Vector3(100,0,0));
assert.ok(hairNode.prev.distanceTo(hairBefore)>0 && hairNode.prev.distanceTo(hairBefore)<.04);
assert.ok(clothNode.prev.equals(clothBefore));
drag.physics.nodes.pop();drag.physics.setStrength(0);
const offBefore=hairNode.prev.clone();drag.physics.applyHairDrag(new THREE.Vector3(1,0,0));
assert.ok(hairNode.prev.equals(offBefore));
console.log('PASS: fallback drag affects only hair, clamps extreme input and respects Off');

const vrmDrag=new Physics(),vrmCenter=new THREE.Object3D();
vrmCenter.position.set(60,20,-5);vrmCenter.scale.setScalar(10);vrmCenter.updateMatrixWorld(true);
const vrmHair={bone:{name:'J_Sec_Hair_01'},center:vrmCenter,_prevTail:new THREE.Vector3(1,2,3)};
const vrmCloth={bone:{name:'Skirt_01'},_prevTail:new THREE.Vector3(1,2,3)};
vrmDrag.attachVrm({scene:new THREE.Group(),springBoneManager:{joints:new Set([vrmHair,vrmCloth])}});
assert.equal(vrmDrag.info.categories.hair,1);
vrmDrag.applyHairDrag(new THREE.Vector3(1,0,0));
assert.ok(Math.abs(vrmHair._prevTail.x-(1+2/600))<1e-10);
assert.deepEqual(vrmCloth._prevTail.toArray(),[1,2,3]);
vrmDrag.setStrength(0);const vrmOff=vrmHair._prevTail.clone();vrmDrag.applyHairDrag(new THREE.Vector3(1,0,0));
assert.ok(vrmHair._prevTail.equals(vrmOff));
vrmDrag.setStrength(1);vrmCenter.scale.setScalar(0);vrmCenter.updateMatrixWorld(true);
vrmDrag.applyHairDrag(new THREE.Vector3(1,0,0));assert.ok(vrmHair._prevTail.equals(vrmOff));
vrmDrag.detach();assert.equal(vrmDrag.vrmHairJoints.length,0);
console.log('PASS: VRM hair-only drag uses scaled center space, respects Off, ignores singular centers and releases old joints');
const unstable=rig();
const duplicate={...unstable.physics.nodes[0],bone:unstable.hinge.clone(),restLocal:unstable.physics.nodes[0].restLocal.clone(),restQuat:unstable.physics.nodes[0].restQuat.clone()};
unstable.model.add(duplicate.bone);unstable.physics.nodes.push(duplicate);
let corrupt=false,disposed=0;
unstable.physics.bullet={update(){for(const n of unstable.physics.nodes)n.bone.quaternion.setFromAxisAngle(new THREE.Vector3(1,0,0),corrupt?3:0);},dispose(){disposed++;for(const n of unstable.physics.nodes)n.bone.quaternion.copy(n.restQuat);}};
unstable.physics.info.engine='Bullet';
for(let i=0;i<30;i++)unstable.physics.update(1/60);
assert.equal(disposed,0,'Stable hair must retain Bullet');
corrupt=true;for(let i=0;i<13;i++)unstable.physics.update(1/60);
assert.equal(disposed,1);assert.equal(unstable.physics.bullet,null);assert.equal(unstable.physics.info.engine,'spring fallback');
assert(unstable.physics.info.warning.includes('Unstable hair'));
console.log('PASS: sustained broken hair falls back safely; valid Bullet hair remains active');

const jitterGuard=new Physics(),jitterRoot=new THREE.Group(),jitterBones=[];
for(let i=0;i<3;i++){
    const bone=new THREE.Bone();bone.name=`スカート_${i}`;bone.position.set(i+1,0,0);jitterRoot.add(bone);jitterBones.push(bone);
}
jitterGuard.model=jitterRoot;
jitterGuard.nodes=jitterBones.map(bone=>({bone,category:'skirt',restLocal:bone.position.clone(),tailLocal:new THREE.Vector3(0,.2,0),restQuat:bone.quaternion.clone(),depth:1,chainDepth:0,phase:0,params:{stiffness:.32,gravity:34,drag:.25,maxAngle:38}}));
jitterGuard.info={source:'model rig',engine:'Bullet',rigidBodies:3,joints:3,chains:1,bones:3,categories:{skirt:3}};
let jitterSign=1,jitterDisposed=0;
jitterGuard.bullet={update(){for(const bone of jitterBones)bone.quaternion.setFromAxisAngle(new THREE.Vector3(0,0,1),.9*jitterSign);jitterSign*=-1;},dispose(){jitterDisposed++;for(const bone of jitterBones)bone.quaternion.identity();}};
jitterGuard._resetBulletJitterGuard();
for(let i=0;i<5;i++)jitterGuard.update(1/60);
assert.equal(jitterDisposed,1,'Sustained multi-bone skirt snaps should release the unstable Bullet solver');
assert.equal(jitterGuard.bullet,null);
assert.equal(jitterGuard.info.engine,'spring fallback');
assert.match(jitterGuard.info.warning,/Unstable hair\/skirt bone motion/);
ui({physics:jitterGuard,physicsInfo:jitterGuard.info},doc,'normal');
assert.ok(status.textContent.includes('safer spring-chain physics is active'));
jitterGuard.setStrength(0);
assert.ok(jitterBones.every((bone,i)=>bone.position.distanceTo(new THREE.Vector3(i+1,0,0))<1e-9&&bone.quaternion.angleTo(new THREE.Quaternion())<1e-9),
    'Turning physics Off after fallback restores the original bone pose');
console.log('PASS: repeated hair/skirt bone jumps automatically switch Bullet rigs to safer spring chains');

// Upper garments must not inherit the loose accessory/hair-sized swing range.
const garmentModel=new THREE.Group(),garment=new THREE.Bone(),garmentTip=new THREE.Bone();
garment.name='RightClothArmR2';garmentTip.name='garmentEnd';garmentTip.position.set(.1,0,0);
garmentModel.add(garment);garment.add(garmentTip);
const garmentPhysics=new Physics();garmentPhysics.attach(garmentModel);
const garmentNode=garmentPhysics.nodes.find(n=>n.bone===garment);
assert.equal(garmentNode.category,'cloth');
for(let i=0;i<240;i++){
    garmentPhysics.update(1/60);
    assert.ok(garment.quaternion.angleTo(garmentNode.restQuat)<=18*Math.PI/180+1e-6);
}
garmentPhysics.disabledBones=new Set([garment]);
for(let i=0;i<120;i++)garmentPhysics.update(1/60);
assert.ok(garment.quaternion.angleTo(garmentNode.restQuat)<1e-6);
assert.equal(garmentNode.pos.distanceTo(garmentNode.prev),0,'Frozen garment cannot accumulate hidden spring velocity');
garmentPhysics.disabledBones.clear();garmentPhysics.update(1/60);
assert.ok(garment.quaternion.angleTo(garmentNode.restQuat)>0,'Restoring garment re-enables its simulation');
console.log('PASS: garment swing bound, true simulation exclusion and unfreeze');
