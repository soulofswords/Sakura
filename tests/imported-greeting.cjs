const assert=require('assert/strict'),fs=require('fs'),vm=require('vm'),THREE=require('../static/vendor/three/build/three.cjs');
const data=JSON.parse(fs.readFileSync('static/assets/animations/hand-raising.json','utf8'));let fail=true,fetches=0;
const context={THREE,fetch:async()=>{fetches++;return {ok:!fail,json:async()=>data};}};
vm.runInNewContext(fs.readFileSync('static/js/imported-greeting.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export default class ImportedGreeting','class ImportedGreeting')+'\nthis.Greeting=ImportedGreeting;',context);
function rig(rotate){
 const root=new THREE.Group();root.rotation.y=rotate;const animationBones={};
 const add=(key,parent,x,y,z)=>{const bone=new THREE.Bone();bone.position.set(x,y,z);parent.add(bone);animationBones[key]={bone,rest:bone.rotation.clone()};return bone;};
 const torso=add('torso',root,0,1,0),chest=add('chest',torso,0,.3,0),neck=add('neck',chest,0,.25,0);add('head',neck,0,.1,0);
 for(const side of ['left','right']){const sign=side==='left'?1:-1,shoulder=add(side+'Shoulder',chest,sign*.15,.15,0),arm=add(side+'Arm',shoulder,sign*.15,0,0),elbow=add(side+'Elbow',arm,sign*.35,0,0);add(side+'Wrist',elbow,sign*.3,0,0);}
 root.updateMatrixWorld(true);return {model:root,animationBones,conversationFingers:[]};
}
(async()=>{
 const first=new context.Greeting(rig(0));await assert.rejects(first.load(),/could not load/);fail=false;await first.load();assert.equal(fetches,2);
 assert.equal(first.data.name,'Hand Raising');assert.ok(first.data.duration>4&&first.data.duration<4.1);
 for(const angle of [0,Math.PI]){
  const v=rig(angle),motion=new context.Greeting(v);await motion.load();assert.equal(fetches,2,'Animation downloaded only once');
  const positions=Object.fromEntries(Object.entries(v.animationBones).map(([k,e])=>[k,e.bone.position.clone()]));
  v.animationBones.rightArm.bone.rotation.z=.2;const before=v.animationBones.rightArm.bone.quaternion.clone(),state=motion.begin();assert.ok(state);assert.ok(before.angleTo(v.animationBones.rightArm.bone.quaternion)<1e-6,'Capturing bind pose cannot visibly reset the character');
  let changed=false;for(let i=0;i<123;i++){motion.apply(state,i/30,1,false);for(const e of state.entries){assert.ok(e.bone.quaternion.toArray().every(Number.isFinite));changed ||= e.bone.quaternion.angleTo(e.rest)>.2;}}
  assert.ok(changed);for(const [key,e]of Object.entries(v.animationBones))assert.ok(e.bone.position.distanceTo(positions[key])<1e-8,'Clip cannot move root or scale limb lengths');
  motion.apply(state,data.duration,0,true);for(const e of state.entries)assert.ok(e.bone.quaternion.angleTo(e.start)<1e-6,'Fade-out ends in original relaxed pose, never import T/A-pose');
  motion.restore(state);for(const e of state.entries)assert.ok(e.bone.quaternion.angleTo(e.start)<1e-6);
  v.userTracking=true;assert.equal(motion.begin(),null);v.userTracking=false;v.live2d={};assert.equal(motion.begin(),null);v.live2d=null;
  const old=v.model;v.model=new THREE.Group();motion.apply(state,1,1,false);assert.equal(state.root,old,'Stale animation never retargets new model');
 }
 console.log('PASS: actual baked FBX samples, load retry/cache, PMX/VRM orientation, finite transforms, bind capture/restore, fixed limb lengths and tracking/Live2D exclusion');
})().catch(e=>{console.error(e);process.exitCode=1;});
