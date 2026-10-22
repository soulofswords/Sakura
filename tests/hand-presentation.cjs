const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),THREE=require('../static/vendor/three/build/three.cjs');
const ctx={THREE};vm.runInNewContext(fs.readFileSync('static/js/hand-presentation.js','utf8').replace(/import .*?;\r?\n/,'').replace('export function presentHand','function presentHand')+'\nthis.present=presentHand;',ctx);
for(const rotation of [0,Math.PI])for(const side of ['left','right']){
 const root=new THREE.Group();root.rotation.y=rotation;root.scale.setScalar(10);
 const torso=new THREE.Bone();root.add(torso);torso.position.y=1;
 const upper=new THREE.Bone(),lower=new THREE.Bone(),hand=new THREE.Bone();
 torso.add(upper);upper.add(lower);lower.add(hand);
 const sign=side==='left'?1:-1;upper.position.set(sign*.23,.3,0);lower.position.x=sign*.3;hand.position.x=sign*.25;
 const bones={torso:{bone:torso},[side+'Arm']:{bone:upper},[side+'Elbow']:{bone:lower},[side+'Wrist']:{bone:hand}};
 const fingers=[];for(const [finger,z]of [[1,.03],[2,0],[4,-.03]]){
  const bone=new THREE.Bone();hand.add(bone);bone.position.set(sign*.09,0,z);fingers.push({bone,finger,segment:0,side});
 }
 const camera=new THREE.PerspectiveCamera();camera.position.set(0,13,50);
 const viewer={model:root,animationBones:bones,conversationFingers:fingers,camera};
 root.updateMatrixWorld(true);const start=hand.getWorldPosition(new THREE.Vector3()),shoulder=upper.getWorldPosition(new THREE.Vector3());
 assert.equal(ctx.present(viewer,side,1),true);root.updateMatrixWorld(true);
 const wrist=hand.getWorldPosition(new THREE.Vector3()),elbow=lower.getWorldPosition(new THREE.Vector3());
 assert.ok(wrist.z>shoulder.z+3,'Hands presented in front, not spread sideways');
 assert.ok(wrist.y>shoulder.y+.8,'Hands raised near shoulder height');
 const angle=elbow.clone().sub(shoulder).normalize().dot(wrist.clone().sub(elbow).normalize());
 assert.ok(angle<.5,'Elbow is visibly bent');assert.ok(wrist.distanceTo(start)>2);
 const middle=hand.worldToLocal(fingers[1].bone.getWorldPosition(new THREE.Vector3())).normalize();
 const across=hand.worldToLocal(fingers[0].bone.getWorldPosition(new THREE.Vector3())).sub(hand.worldToLocal(fingers[2].bone.getWorldPosition(new THREE.Vector3()))).normalize();
 const normal=new THREE.Vector3().crossVectors(across,middle).multiplyScalar(sign).transformDirection(hand.matrixWorld);
 assert.ok(normal.dot(new THREE.Vector3(0,0,1))>.9,'Palm faces the viewer');
 assert.ok([upper,lower,hand].every(b=>b.quaternion.toArray().every(Number.isFinite)));
}
console.log('PASS: bent elbows, hands forward and raised, palms facing viewer across mirrored and rotated arm chains');
