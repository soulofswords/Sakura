const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),THREE=require('../static/vendor/three/build/three.cjs');
const ctx={THREE,console,ImportedGreeting:class{constructor(){this.data={duration:4.067};}async load(){}begin(){return {};}apply(){}restore(){}}};vm.runInNewContext(fs.readFileSync('static/js/hand-presentation.js','utf8').replace(/import .*?;\r?\n/,'').replace('export function presentHand','function presentHand'),ctx);
vm.runInNewContext(fs.readFileSync('static/js/model-dance.js','utf8').replace(/^import .*?;\r?\n/gm,'').replace('export default class ModelDance','class ModelDance')+'\nthis.Dance=ModelDance;',ctx);
for(const format of ['pmx','vrm'])for(const style of ['groove','step','wave']){
 const model=new THREE.Group();model.position.set(1,2,3);const v={model,vrm:format==='vrm'?{}:null,physics:{},animationBones:{},_avoidArmClipping(){}};
 for(const name of ['torso','chest','head','leftArm','rightArm','leftElbow','rightElbow','leftWrist','rightWrist','leftThigh','rightThigh','leftKnee','rightKnee'])v.animationBones[name]={bone:new THREE.Bone(),rest:new THREE.Euler()};
 const dance=new ctx.Dance(v);assert.equal(dance.start(style),true);let low=Infinity,high=-Infinity;
 for(let i=0;i<400;i++){dance.update(1/60);low=Math.min(low,v.animationBones.torso.bone.rotation.z);high=Math.max(high,v.animationBones.torso.bone.rotation.z);for(const e of Object.values(v.animationBones))assert.ok(e.bone.quaternion.toArray().every(Number.isFinite));assert.ok(model.position.distanceTo(new THREE.Vector3(1,2,3))<.6);}
 assert.ok(low<-.02&&high>.02);dance.stop();for(let i=0;i<180;i++)dance.update(1/60);assert.equal(dance.active,null);assert.deepEqual(model.position.toArray(),[1,2,3]);
 dance.start();for(let i=0;i<1500;i++)dance.update(1/60);assert.equal(dance.active,null,'Automatic finish');
 v.vtuberTrackingMode=true;assert.equal(dance.start(),false);v.vtuberTrackingMode=false;v.live2d={};assert.equal(dance.start(),false);
}
console.log('PASS: three routines on PMX/VRM, bounded finite poses, fade/restore, automatic finish, tracking and Live2D exclusions');
for(const vrm of [false,true])for(const style of ['victory','defeat']){
 const model=new THREE.Group();model.position.set(1,2,3);
 const v={model,vrm,physics:{},animationBones:{},_avoidArmClipping(){}};
 for(const key of ['torso','chest','neck','head','leftArm','rightArm','leftElbow','rightElbow','leftThigh','rightThigh','leftKnee','rightKnee']){
  const bone=new THREE.Bone();model.add(bone);if(key==='head')bone.position.y=2;
  v.animationBones[key]={bone,rest:new THREE.Euler()};
 }
 const dance=new ctx.Dance(v);assert.equal(dance.start(style),true);let peak=0,head=0;
 for(let i=0;i<400;i++){
  dance.update(1/60);peak=Math.max(peak,model.position.y-2);head=Math.max(head,v.animationBones.head.bone.rotation.x);
  assert.ok(model.position.toArray().every(Number.isFinite));
  for(const e of Object.values(v.animationBones))assert.ok(e.bone.quaternion.toArray().every(Number.isFinite));
 }
 if(style==='victory')assert.ok(peak>.02&&peak<.2);else {assert.equal(peak,0);assert.ok(head>.1);}
 assert.equal(dance.active,null);assert.deepEqual(model.position.toArray(),[1,2,3]);
 dance.start(style);v.model=new THREE.Group();dance.update(1/60);assert.equal(dance.active,null,'Model switch cancels reaction');
 v.userTracking=true;assert.equal(dance.start(style),false);
}
console.log('PASS: victory jump and defeat head-down on PMX/VRM, bounded motion, automatic neutral return, model-switch cancellation');
for(const vrm of [false,true]){
 const signatures=new Set();
 for(const style of ['groove','step','wave','twist','disco','march']){
  const model=new THREE.Group(),viewer={model,vrm,physics:{},animationBones:{},_avoidArmClipping(){}};
  for(const key of ['torso','chest','head','leftArm','rightArm','leftElbow','rightElbow','leftWrist','rightWrist','leftThigh','rightThigh','leftKnee','rightKnee'])viewer.animationBones[key]={bone:new THREE.Bone(),rest:new THREE.Euler()};
  const dance=new ctx.Dance(viewer);assert.ok(dance.start(style));
  for(let i=0;i<45;i++)dance.update(1/60);
  const values=[...model.position.toArray(),...Object.values(viewer.animationBones).flatMap(e=>e.bone.rotation.toArray().slice(0,3))];
  assert.ok(values.every(Number.isFinite));signatures.add(JSON.stringify(values));
  dance.stop(true);assert.deepEqual(model.position.toArray(),[0,0,0]);
 }
 assert.equal(signatures.size,6,'All six routines must produce different poses and root motion');
}
for(const vrm of [false,true])for(const style of ['hands_both','hand_left','hand_right']){
 const model=new THREE.Group(),v={model,vrm,physics:{},animationBones:{},_avoidArmClipping(){}};
 for(const key of ['torso','chest','head','leftArm','rightArm','leftElbow','rightElbow','leftWrist','rightWrist'])
  v.animationBones[key]={bone:new THREE.Bone(),rest:new THREE.Euler()};
 const motion=new ctx.Dance(v);assert.ok(motion.start(style));
 for(let i=0;i<120;i++)motion.update(1/60);
 for(const e of Object.values(v.animationBones))assert.ok(e.bone.quaternion.toArray().every(Number.isFinite));
 for(let i=0;i<400;i++)motion.update(1/60);
 assert.equal(motion.active,null);assert.deepEqual(model.position.toArray(),[0,0,0]);
 v.userTracking=true;assert.equal(motion.start(style),false);
}
console.log('PASS: both/left/right hand gestures, smooth completion and tracking isolation on PMX/VRM');
for(const vrm of [false,true])for(const style of ['laugh','laugh_bend']){
 const model=new THREE.Group(),v={model,vrm,physics:{},animationBones:{},_avoidArmClipping(){}};
 for(const key of ['torso','chest','neck','head','leftArm','rightArm','leftElbow','rightElbow','leftWrist','rightWrist','leftThigh','rightThigh','leftKnee','rightKnee']){
  const bone=new THREE.Bone();model.add(bone);v.animationBones[key]={bone,rest:new THREE.Euler()};
 }
 const motion=new ctx.Dance(v);assert.ok(motion.start(style));let bend=0;
 for(let i=0;i<600;i++){
  motion.update(1/60);bend=Math.max(bend,Math.abs(v.animationBones.torso.bone.rotation.x));
  for(const e of Object.values(v.animationBones))assert.ok(e.bone.quaternion.toArray().every(Number.isFinite));
 }
 assert.ok(bend>(style==='laugh_bend'?.3:.04));assert.equal(motion.active,null);
 for(const e of Object.values(v.animationBones))assert.ok(e.bone.quaternion.angleTo(new THREE.Quaternion())<1e-6);
 assert.deepEqual(model.position.toArray(),[0,0,0]);
 v.userTracking=true;assert.equal(motion.start(style),false);v.userTracking=false;v.live2d={};assert.equal(motion.start(style),false);
}
console.log('PASS: short/deep laugh on PMX/VRM, finite bends, complete neutral return, tracking and Live2D exclusions');
for(const vrm of [false,true]){
 const model=new THREE.Group(),v={model,vrm,physics:{},animationBones:{}};
 for(const key of ['torso','chest','neck','head','leftArm','rightArm','leftElbow','rightElbow','leftWrist','rightWrist']){
  const bone=new THREE.Bone();model.add(bone);v.animationBones[key]={bone,rest:new THREE.Euler()};
 }
 const motion=new ctx.Dance(v);assert.ok(motion.start('chest_tap'));
 for(let i=0;i<400;i++){motion.update(1/60);for(const e of Object.values(v.animationBones))assert.ok(e.bone.quaternion.toArray().every(Number.isFinite));}
 assert.equal(motion.active,null);assert.deepEqual(model.position.toArray(),[0,0,0]);
 delete v.animationBones.rightWrist;assert.equal(motion.start('chest_tap'),false);
}
console.log('PASS: chest tap restores neutral, remains finite, and requires a wrist rig');
for(const vrm of [false,true]){
 const model=new THREE.Group(),v={model,vrm,physics:{},animationBones:{}};
 for(const key of ['torso','chest','neck','head','leftArm','rightArm','leftElbow','rightElbow','leftWrist','rightWrist']){
  const bone=new THREE.Bone();model.add(bone);v.animationBones[key]={bone,rest:new THREE.Euler()};
 }
 const motion=new ctx.Dance(v);assert.ok(motion.start('greeting_wave'));
 for(let i=0;i<400;i++){motion.update(1/60);for(const e of Object.values(v.animationBones))assert.ok(e.bone.quaternion.toArray().every(Number.isFinite));}
 assert.equal(motion.active,null);assert.deepEqual(model.position.toArray(),[0,0,0]);
 v.userTracking=true;assert.equal(motion.start('greeting_wave'),false);v.userTracking=false;v.live2d={};assert.equal(motion.start('greeting_wave'),false);
}
console.log('PASS: greeting wave remains finite, completes smoothly and excludes Live2D/face tracking');
{
 const model=new THREE.Group(),v={model,vrm:false,userTracking:true,vtuberTrackingMode:true,physics:{},animationBones:{}};
 for(const key of ['torso','chest','neck','head','leftArm','rightArm','leftElbow','rightElbow','leftWrist','rightWrist']){const bone=new THREE.Bone();model.add(bone);v.animationBones[key]={bone,rest:new THREE.Euler()};}
 const motion=new ctx.Dance(v);assert.equal(motion.start('hands_both'),false);
 assert.equal(motion.start('hands_both',{manual:true}),true);
 for(let i=0;i<400;i++)motion.update(1/60);
 assert.equal(motion.active,null);assert.equal(v.userTracking,true);assert.equal(v.vtuberTrackingMode,true);assert.equal(motion.supported(),false);
 console.log('PASS: explicitly paired phone pose can temporarily override tracking and then restore normal tracking eligibility');
}
