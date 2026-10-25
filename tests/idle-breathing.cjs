const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const ctx={};vm.runInNewContext(fs.readFileSync('static/js/idle-breathing.js','utf8').replace(/export /g,'')+';this.apply=applyIdleBreathing;this.restore=restoreIdleBreathing;',ctx);
const bone={rotation:{x:.2},scale:{x:1,y:1,z:1}};
const viewer={model:{},animationBones:{chest:{bone}},activity:'idle',vtuberTrackingMode:true};
let min=1,max=-1;
for(let i=0;i<3600;i++){ctx.restore(viewer);ctx.apply(viewer,1/60,i/60);min=Math.min(min,bone.rotation.x);max=Math.max(max,bone.rotation.x);}
assert.ok(min<.193&&max>.207&&min>=.191-1e-9&&max<=.209+1e-9,'Bounded breath repeats without pose drift');
ctx.restore(viewer);assert.equal(bone.rotation.x,.2);assert.equal(bone.scale.y,1,'No torso elongation');
viewer.userTracking=true;ctx.apply(viewer,1/60,2);assert.equal(bone.rotation.x,.2,'Tracking owns the pose');
viewer.userTracking=false;viewer.dance={active:{}};ctx.apply(viewer,1/60,2);assert.equal(bone.rotation.x,.2,'Dance and hello wave own the pose');
console.log('PASS: gentle repeatable breathing, no accumulated rotation or stretching, tracking and greeting isolation.');
