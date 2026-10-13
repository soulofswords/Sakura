const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),THREE=require('../static/vendor/three/build/three.cjs');
const ctx={};vm.runInNewContext(fs.readFileSync('static/js/chat-reader-motion.js','utf8').replace(/export /g,'')+'\nthis.apply=applyChatReaderLean;',ctx);
for(const format of ['PMX','VRM']){
    const viewer={physics:{},animationBones:Object.fromEntries(['torso','chest','neck','head','leftArm'].map(key=>[key,{bone:new THREE.Bone(),rest:new THREE.Euler()}]))};
    assert.equal(ctx.apply(viewer,1/60),false,'Ordinary VTuber mode has no scripted lean');viewer.chatReaderActive=true;
    let min=Infinity,max=-Infinity;
    for(let frame=0;frame<1800;frame++){ctx.apply(viewer,1/60);const angle=viewer.animationBones.torso.bone.rotation.z;min=Math.min(min,angle);max=Math.max(max,angle);}
    assert.ok(min<-.03&&max>.03,format+' keeps alternating after speech');assert.ok(max<.036&&min>-.036);assert.equal(viewer.animationBones.leftArm.bone.rotation.z,0,'No AI hand gestures');
    viewer.chatReaderActive=false;for(let frame=0;frame<400;frame++)ctx.apply(viewer,1/60);
    assert.equal(viewer.chatReaderMotion,null);assert.equal(viewer.animationBones.torso.bone.rotation.z,0,'Stop restores neutral');
    viewer.userTracking=true;viewer.chatReaderActive=true;assert.equal(ctx.apply(viewer,1/60),false,'Webcam owns pose');
}
const liveSource=fs.readFileSync('static/js/live2d-viewer.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export default class Live2DViewer','class Live2DViewer');
vm.runInNewContext(liveSource+'\nthis.Live=Live2DViewer;',ctx);
const params={},live=Object.create(ctx.Live.prototype);Object.assign(live,{renderDelta:1/60,filtered:{},values:{A:.2},owner:{vtuberTrackingMode:true,chatReaderActive:true,activity:'talking'},avatar:{internalModel:{coreModel:{getParameterIndex(){return 0;},setParameterValueById(id,value){params[id]=value;}}}}});
let low=Infinity,high=-Infinity;for(let frame=0;frame<1200;frame++){live.applyParameters();low=Math.min(low,params.ParamBodyAngleZ);high=Math.max(high,params.ParamBodyAngleZ);}
assert.ok(low<-1.7&&high>1.7,'Live2D body shifts in both directions');assert.ok(params.ParamMouthOpenY>.19,'Lean preserves lip sync');
const changes=[];vm.runInNewContext(fs.readFileSync('static/js/chat-reader.js','utf8').replace('export default class ChatReader','class ChatReader')+'\nthis.Reader=ChatReader;',ctx);
const reader=new ctx.Reader({stopAudio(){},onEnabled:enabled=>changes.push(enabled)});reader.start();reader.stop();assert.deepEqual(changes,[false,true,false]);
console.log('PASS: Chat Reader-only PMX/VRM/Live2D continuous bounded lean, neutral stop, mouth and webcam isolation');
