const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),THREE=require('../static/vendor/three/build/three.cjs');
const ctx={THREE,performance};vm.runInNewContext(fs.readFileSync('static/js/avatar-retarget.js','utf8').replace(/^import .*;\r?\n/gm,'').replace(/export function /g,'function ').replace('export default class AvatarRetarget','class AvatarRetarget')+'\nthis.Rig=AvatarRetarget;',ctx);
for(const vrm of [null,{humanoid:{getNormalizedBoneNode(){return null;}}}])for(const mirror of [true,false]){
 const root=new THREE.Group(),head=new THREE.Bone();root.add(head);
 const viewer={model:root,vrm,morphMap:{},userTrackingMirror:mirror,animationBones:{head:{bone:head,rest:new THREE.Euler()}},setMorph(){}};
 const rig=new ctx.Rig(viewer);rig.calibrated=true;rig.neutral.set(0,0,0);
 const frame=pitch=>({face:{landmarks:[{}],matrix:new THREE.Matrix4().makeRotationX(pitch).toArray(),blendshapes:[]},hands:[],receivedAt:performance.now()});
 for(let i=0;i<40;i++)rig.apply(frame(.3),1/60);assert.ok(head.rotation.x*(vrm?-1:1)>.25,'Looking up/down uses format-specific pitch, independent of mirror');
 for(let i=0;i<80;i++)rig.apply(frame(-.3),1/60);assert.ok(head.rotation.x*(vrm?-1:1)<-.25,'Opposite pitch follows the user');
 rig.calibrate(frame(-.3));for(let i=0;i<80;i++)rig.apply(frame(-.3),1/60);assert.ok(Math.abs(head.rotation.x)<.01,'Calibration restores neutral');
}
console.log('PASS: VRM pitch corrected, PMX preserved, mirrored/unmirrored pitch and calibration');
