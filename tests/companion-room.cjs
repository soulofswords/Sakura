const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),THREE=require('../static/vendor/three/build/three.cjs');
const ctx={THREE,console};vm.runInNewContext(fs.readFileSync('static/js/companion-room.js','utf8').replace(/^import .*;\r?\n/gm,'').replaceAll('export ','')+';this.Room=CompanionRoom;',ctx);
for(const vrm of [false,true]){
 const model=new THREE.Group();model.add(new THREE.Mesh(new THREE.BoxGeometry(1,2,1)));model.position.set(3,2,1);
 const viewer={model,vrm,scene:new THREE.Scene(),camera:new THREE.PerspectiveCamera(),controls:{target:new THREE.Vector3(0,1,0),update(){}},animationBones:{}};
 for(const key of ['torso','head','leftArm','rightArm','leftElbow','rightElbow','leftWrist','rightWrist','leftThigh','rightThigh','leftKnee','rightKnee']){const bone=new THREE.Bone();model.add(bone);viewer.animationBones[key]={bone};}
 const room=new ctx.Room(viewer);assert.deepEqual([...room.capabilities()],[]);room.enable();assert.equal(viewer.scene.children.length,1);
 for(const action of ['desk','mirror','bed','home','nod','shake_head','stretch']){
  room.stop();assert(room.act(action));
  for(let n=0;n<1000;n++){room.update(1/60);assert(model.position.toArray().every(Number.isFinite));assert(model.quaternion.toArray().every(Number.isFinite));for(const e of Object.values(viewer.animationBones))assert(e.bone.quaternion.toArray().every(Number.isFinite));}
  assert.equal(room.pose,null);if(action==='bed')assert(Math.abs(model.rotation.x)>1.5);if(action==='desk')assert(model.position.x<3);if(action==='bed'){model.updateMatrixWorld(true);const center=new THREE.Box3().setFromObject(model).getCenter(new THREE.Vector3());assert.ok(Math.abs(center.x-(room.center.x+1.05*room.height))<.001,'Body is centred across the mattress');assert.ok(Math.abs(center.z-(room.center.z-.62*room.height))<.001,'Body lies along the bed length');}
 }
 room.stop();room.act('bed');for(let i=0;i<1000;i++)room.update(1/60);assert.equal(room.sleeping,true);assert.deepEqual([...room.capabilities()],['home']);assert(!room.act('desk'),'Sleep permits only waking');assert(room.act('home'));assert.equal(room.sleeping,false);assert(room.pose.rise,'Wake includes a get-up transition');for(let i=0;i<1000;i++)room.update(1/60);assert.deepEqual(model.position.toArray(),room.base.toArray());
 assert(!room.act('delete files'));room.act('desk');room.update(0/0);assert(model.position.toArray().every(Number.isFinite));
 viewer.dance={active:{style:'greeting_wave'}};room.update(1/60);assert.equal(viewer.dance.active.style,'greeting_wave');assert.equal(room.pose,null);assert(!room.act('bed'));viewer.dance=null;
 room.act('desk');viewer.userTracking=true;room.update(1/60);assert.equal(room.pose,null);assert.deepEqual(model.position.toArray(),[3,2,1]);assert(!room.act('bed'));viewer.userTracking=false;
 room.disable();assert.equal(viewer.scene.children.length,0);assert.deepEqual(model.position.toArray(),[3,2,1]);
 room.enable();room.act('desk');viewer.model=new THREE.Group();room.update(.02);assert(!room.enabled);assert.deepEqual(viewer.model.position.toArray(),[0,0,0]);
 viewer.model=model;viewer.userTracking=false;
 const stage=new THREE.Group();stage.position.set(1,0,0);stage.scale.setScalar(2);stage.updateMatrixWorld(true);
 viewer.pmxStage={enabled:true,selected:'stage1',records:[{id:'stage1',path:'pmx/Stages/room/room.pmx'}],meshes:new Map([['stage1',stage]])};
 room.enable('imported');assert.equal(room.room,null,'Imported mode does not add the procedural room');
 assert(!room.capabilities().includes('desk'),'Unmarked furniture is not advertised to the model');
 model.position.set(4,2,1);room.mark('desk');room.stop();assert(room.capabilities().includes('desk'));
 stage.position.x+=1;stage.updateMatrixWorld(true);assert(room.act('desk'));
 assert.ok(Math.abs(room.pose.target.x-5)<1e-6,'Marked points follow the stage transform');
 for(let i=0;i<1000;i++)room.update(1/60);
 assert.ok(Math.abs(model.position.x-5)<1e-6,'PMX/VRM actually reaches the marked furniture point');
 room.stop();model.position.x=1000;room.mark('mirror');room.stop();assert(!room.act('mirror'),'Distant destinations are refused');
 viewer.pmxStage.enabled=false;room.update(.016);assert(!room.enabled,'Disabling stage stops motion');
 viewer.live2d={};assert.throws(()=>room.enable(),/rigged/);
}
console.log('PASS: PMX/VRM room locomotion and poses, finite transforms, stop/restore, tracking priority, hello preservation, scene disposal and model changes.');
