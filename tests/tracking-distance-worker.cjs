const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
(async()=>{
const messages=[],faceStamps=[],handsStamps=[];let facePresent=true,closed=0;
const smallFace=Array.from({length:478},(_,i)=>({x:.49+(i%4)*.002,y:.2+(i%5)*.003,z:-.01}));
const face={detectForVideo(surface,stamp){assert.ok(!faceStamps.length||stamp>faceStamps.at(-1));faceStamps.push(stamp);return{faceLandmarks:facePresent?[surface.width===512?smallFace.map(p=>({...p,x:.5,y:.5})):smallFace]:[],faceBlendshapes:[{categories:[]}],facialTransformationMatrixes:[]};}};
const hand={detectForVideo(surface,stamp){assert.ok(!handsStamps.length||stamp>handsStamps.at(-1));handsStamps.push(stamp);return{landmarks:[],worldLandmarks:[],handedness:[]};},close(){}};
const pose={detectForVideo(){return{landmarks:[],worldLandmarks:[]};},close(){}};
const tasks={FilesetResolver:{forVisionTasks:async()=>({})},FaceLandmarker:{createFromOptions:async()=>face},HandLandmarker:{createFromOptions:async()=>hand},PoseLandmarker:{createFromOptions:async()=>pose}};
const ctx={tasks,self:{postMessage:data=>messages.push(data)},importScripts(){},OffscreenCanvas:class{constructor(w,h){this.width=w;this.height=h;}getContext(){return{drawImage(){}};}}};
vm.runInNewContext(fs.readFileSync('static/js/tracking-distance.js','utf8'),ctx);
const worker=fs.readFileSync('static/js/avatar-tracking-worker.js','utf8').replace("await import('/static/vendor/tracking/vision_bundle.mjs?v=2')",'tasks');vm.runInNewContext(worker,ctx);
await ctx.self.onmessage({data:{type:'init',handsEnabled:false}});assert.equal(messages.at(-1).type,'ready');
for(let i=0;i<10;i++){await ctx.self.onmessage({data:{type:'frame',timestamp:1000+i*80,image:{width:1280,height:720,close(){closed++;}}}});const result=messages.at(-1);assert.equal(result.type,'result');assert.equal(result.distanceAssist.width,960);assert.equal(result.distanceAssist.height,540);assert.equal(result.hands.length,0);assert.equal(result.handTrackingEnabled,false);}
assert.ok(messages.some(m=>m.distanceAssist?.faceZoomed));assert.equal(closed,10);assert.equal(handsStamps.length,0,'Hand toggle remains off');
facePresent=false;for(let i=10;i<13;i++)await ctx.self.onmessage({data:{type:'frame',timestamp:1000+i*80,image:{width:1280,height:720,close(){closed++;}}}});
assert.equal(messages.at(-1).face.landmarks.length,0,'Lost face never reuses stale landmarks');assert.ok(!messages.some(m=>m.type==='error'));console.log('PASS: worker HD aspect, automatic face crop, fresh full-frame reacquisition, strictly increasing timestamps, face loss, disabled hands and bitmap cleanup');
})().catch(e=>{console.error(e);process.exitCode=1;});
