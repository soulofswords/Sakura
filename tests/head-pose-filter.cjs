const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),THREE=require('../static/vendor/three/build/three.cjs');
const ctx={THREE};vm.runInNewContext(fs.readFileSync('static/js/head-pose-filter.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export default class HeadPoseFilter','class HeadPoseFilter')+'\nthis.Filter=HeadPoseFilter;',ctx);
const face=angle=>({landmarks:[{}],matrix:new THREE.Matrix4().makeRotationY(angle).toArray(),blendshapes:[{categoryName:'jawOpen',score:.5}]});
const rotation=result=>new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().fromArray(result.matrix));
const filter=new ctx.Filter();filter.update(face(0),1000,{});
let result=filter.update(face(1.4),1067,{faceZoomed:true});assert.ok(rotation(result).angleTo(new THREE.Quaternion())<1e-9,'One-frame distant spike is rejected');
result=filter.update(face(0),1134,{faceZoomed:true});assert.ok(rotation(result).angleTo(new THREE.Quaternion())<1e-9,'Head remains neutral after isolated spike');
let previous=new THREE.Quaternion();for(let i=0;i<12;i++){result=filter.update(face(.8),1200+i*67,{faceZoomed:true});const next=rotation(result);assert.ok(previous.angleTo(next)<.27,'Real turn cannot jump by more than the velocity bound');previous=next;}
assert.ok(rotation(result).angleTo(new THREE.Quaternion())>.65,'Sustained real movement remains responsive');assert.equal(result.blendshapes[0].score,.5,'Pose smoothing leaves mouth data intact');
filter.reset();filter.update(face(Math.PI-.01),3000,{});result=filter.update(face(-Math.PI+.01),3067,{});assert.ok(rotation(result).angleTo(rotation(face(Math.PI-.01)))<.025,'Quaternion path crosses angle wrap smoothly');
assert.equal(filter.update({...face(0),matrix:Array(16).fill(NaN)},3100,{}).matrix,null,'Invalid detector matrices cannot corrupt the model');
console.log('PASS: distant pose spikes, sustained motion, angular velocity bound, wrap continuity and facial signal preservation');
