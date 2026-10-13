const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
(async()=>{
const messages=[],faceStamps=[],handsStamps=[];let facePresent=true,closed=0;
const smallFace=Array.from({length:478},(_,i)=>({x:.49+(i%4)*.002,y:.2+(i%5)*.003,z:-.01}));
const face={detectForVideo(surface,stamp){assert.ok(!faceStamps.length||stamp>faceStamps.at(-1));faceStamps.push(stamp);return{faceLandmarks:facePresent?[surface.width===512?smallFace.map(p=>({...p,x:.5,y:.5})):smallFace]:[],faceBlendshapes:[{categories:[]}],facialTransformationMatrixes:[]};}};
const hand={detectForVideo(surface,stamp){assert.ok(!handsStamps.length||stamp>handsStamps.at(-1));handsStamps.push(stamp);return{landmarks:[],worldLandmarks:[],handedness:[]};},close(){}};
let poseCalls=0;
const pose={detectForVideo(){poseCalls++;return{landmarks:[],worldLandmarks:[]};},close(){}};
const detectorWidths=[];
const identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],cropped=[0,0,-1,0,0,1,0,0,1,0,0,0,0,0,0,1];
const tasks={FilesetResolver:{forVisionTasks:async()=>({})},FaceLandmarker:{createFromOptions:async()=>{const widths=[];detectorWidths.push(widths);return {detectForVideo(surface,stamp){widths.push(surface.width);const result=face.detectForVideo(surface,stamp);result.facialTransformationMatrixes=[{data:surface.width===512?cropped:identity}];return result;}};}},HandLandmarker:{createFromOptions:async()=>hand},PoseLandmarker:{createFromOptions:async()=>pose}};
const ctx={tasks,self:{postMessage:data=>messages.push(data)},importScripts(){},OffscreenCanvas:class{constructor(w,h){this.width=w;this.height=h;}getContext(){return{drawImage(){}};}}};
vm.runInNewContext(fs.readFileSync('static/js/tracking-distance.js','utf8'),ctx);
const worker=fs.readFileSync('static/js/avatar-tracking-worker.js','utf8').replace("await import('/static/vendor/tracking/vision_bundle.mjs?v=2')",'tasks');vm.runInNewContext(worker,ctx);
await ctx.self.onmessage({data:{type:'init',handsEnabled:false}});assert.equal(messages.at(-1).type,'ready');
for(let i=0;i<10;i++){await ctx.self.onmessage({data:{type:'frame',timestamp:1000+i*80,image:{width:1280,height:720,close(){closed++;}}}});const result=messages.at(-1);assert.equal(result.type,'result');assert.equal(result.distanceAssist.width,960);assert.equal(result.distanceAssist.height,540);assert.equal(result.hands.length,0);assert.equal(result.handTrackingEnabled,false);}
assert.ok(messages.some(m=>m.distanceAssist?.faceZoomed));assert.equal(closed,10);assert.equal(handsStamps.length,0,'Hand toggle remains off');
assert.ok(detectorWidths[0].every(width=>width===960),'Primary tracker never changes camera geometry');assert.ok(detectorWidths[1].every(width=>width===512),'Crop tracker has independent temporal state');
for(const message of messages.filter(m=>m.type==='result'))assert.deepEqual(message.face.matrix,identity,'Zoomed mouth/eyes never replace full-frame head pose');
facePresent=false;for(let i=10;i<13;i++)await ctx.self.onmessage({data:{type:'frame',timestamp:1000+i*80,image:{width:1280,height:720,close(){closed++;}}}});
assert.equal(messages.at(-1).face.landmarks.length,0,'Lost face never reuses stale landmarks');assert.ok(!messages.some(m=>m.type==='error'));console.log('PASS: worker HD aspect, automatic face crop, fresh full-frame reacquisition, strictly increasing timestamps, face loss, disabled hands and bitmap cleanup');
await ctx.self.onmessage({data:{type:'hands-enabled',enabled:true}});
const frame=async(i,bodyTracking)=>ctx.self.onmessage({data:{type:'frame',timestamp:1000+i*80,bodyTracking,image:{width:1280,height:720,close(){closed++;}}}});
await frame(13,false);assert.equal(poseCalls,0);assert.equal(handsStamps.length,0,'Live2D skips unused body inference');
await frame(14,true);assert.equal(poseCalls,1);assert.ok(handsStamps.length>0,'Switching to 3D resumes body inference');
const priorHands=handsStamps.length;await frame(15,false);assert.equal(poseCalls,1);assert.equal(handsStamps.length,priorHands,'Switching back to Live2D skips body again');
console.log('PASS: Live2D face-only inference and immediate 3D body restoration preserve hand preference');
})().catch(e=>{console.error(e);process.exitCode=1;});
