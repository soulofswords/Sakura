const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),THREE=require('../static/vendor/three/build/three.cjs');
const ctx={};vm.runInNewContext(fs.readFileSync('static/js/model-dance.js','utf8').replace('export default class ModelDance','class ModelDance')+'\nthis.Dance=ModelDance;',ctx);
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
