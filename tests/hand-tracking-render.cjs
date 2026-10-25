// Live regression: a confirmed webcam hand carries world landmarks, and the wrist
// palm branch used to raise a ReferenceError inside the render loop. model-viewer.js
// disposes the model on any frame exception, so the avatar vanished until reload.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
const BASE=process.env.SAKURA_LIVE_URL||'http://127.0.0.1:8767';
const EXECUTABLE=process.env.AUDIT_CHROMIUM||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';

(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:EXECUTABLE,args:['--use-angle=d3d11']});
 try{
  const page=await browser.newPage({viewport:{width:520,height:640}});
  // The harness page is only a way to reach a running Sakura server's own modules,
  // so it is supplied locally and every module, model and API comes from that server.
  await page.route('**/static/library-audit.html',route=>route.fulfill({status:200,
   headers:{'content-type':'text/html'},body:fs.readFileSync('static/library-audit.html','utf8')}));
  const pageErrors=[];page.on('pageerror',error=>pageErrors.push(String(error)));
  await page.goto(`${BASE}/static/library-audit.html`);
  await page.waitForFunction(()=>window.auditReady,null,{timeout:60000});
  const model=await page.evaluate(async()=>{
   const list=(await (await fetch('/api/models')).json()).models;
   const pick=list.find(entry=>entry.path.toLowerCase().endsWith('.vrm'))||list.find(entry=>entry.path.toLowerCase().endsWith('.pmx'));
   if(!pick)throw new Error('No VRM or PMX model is available to load.');
   await window.auditViewer.loadModel('/models/'+pick.path.split('/').map(encodeURIComponent).join('/'));
   return pick.path;
  });
  console.log(`Loaded ${model} in the live viewer`);
  const result=await page.evaluate(async()=>{
   const viewer=window.auditViewer;
   let vanished=null;
   const listener=event=>{vanished=String(event.detail);};
   window.addEventListener('sakura-model-render-error',listener);
   const landmarks=Array.from({length:21},(_,i)=>({x:.3+i*.01,y:.6-i*.01,z:0}));
   landmarks[5]={x:.21,y:.6,z:0};landmarks[17]={x:.29,y:.6,z:0};
   const hand=bent=>({side:'Left',confidence:.99,landmarks:landmarks.map(p=>({...p})),
    world:landmarks.map((p,i)=>({x:p.x,y:p.y,z:bent?(i===0?-.22:i===9?.22:0):0}))});
   viewer.setUserTracking(true);
   const wrist=viewer.animationBones.leftWrist?.bone;
   if(!wrist)throw new Error('The loaded rig has no left wrist bone to retarget.');
   const starting=wrist.quaternion.toArray().slice();
   let stamp=Date.now();
   for(let frame=0;frame<16;frame++){
    // Two distinct stamps confirm a hand; the palm orientation is read after that.
    viewer.updateUserTracking({receivedAt:performance.now(),timestamp:++stamp,handTrackingEnabled:true,
     face:{landmarks:[],blendshapes:[]},hands:[hand(frame>3)],pose:null});
    await new Promise(resolve=>setTimeout(resolve,60));
   }
   const out={vanished,hasModel:!!viewer.model,tracking:!!viewer.userTracking,
    wristDelta:Math.hypot(...wrist.quaternion.toArray().map((value,index)=>value-starting[index])),
    finite:Object.values(viewer.animationBones).every(entry=>entry.bone.quaternion.toArray().every(Number.isFinite))};
   window.removeEventListener('sakura-model-render-error',listener);
   return out;
  });
  assert.equal(pageErrors.length,0,'The live page must not raise: '+pageErrors.join(' | '));
  assert.equal(result.vanished,null,'A hand-tracking frame must not stop model rendering: '+(result.vanished||''));
  assert.equal(result.hasModel,true,'The loaded model must still exist after hand tracking frames');
  assert.equal(result.tracking,true,'User tracking must stay enabled');
  assert.equal(result.finite,true,'Every retargeted bone must stay finite');
  assert(result.wristDelta>.01,'A rotated palm must turn the wrist, quaternion delta '+result.wristDelta);
  console.log('PASS: confirmed hands with world landmarks keep the model rendered and turn the wrist');
 }finally{await browser.close();}
})().catch(error=>{console.error(error.message||error);process.exitCode=1;});
