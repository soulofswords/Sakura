const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.AUDIT_CHROMIUM,args:['--use-angle=d3d11']});
 try{
  const page=await browser.newPage({viewport:{width:640,height:800}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8766/static/physics-check.html');await page.waitForFunction(()=>window.viewer?.physics);
  const results=await page.evaluate(async()=>{
   const v=window.viewer;v.animate=()=>{};await new Promise(r=>setTimeout(r,50));
   const inventory=(await(await fetch('/api/models')).json()).models.filter(m=>m.path.toLowerCase().endsWith('.vrm')),out=[];
   for(const model of inventory){
    await v.loadModel('/models/'+model.path.split('/').map(encodeURIComponent).join('/'));
    v.physicsBoost=0;v.setActivity('idle');v.setPhysicsStrength(1);v.setWindStrength(0);
    const tick=()=>{v._animateCharacter(1/60,0);v.vrm.update(1/60);};for(let i=0;i<120;i++)tick();
    const hair=v.physics.vrmHairJoints,all=[...v.vrm.springBoneManager?.joints||[]],other=all.filter(j=>!hair.includes(j));
    const before=hair.map(j=>j.bone.quaternion.clone()),settings=all.map(j=>JSON.stringify(j.settings));
    const otherBefore=other.map(j=>j._prevTail.clone());
    v.applyHairScreenDrag(12,4);const otherIsolated=other.every((j,i)=>j._prevTail.equals(otherBefore[i]));
    let response=0;
    for(let i=0;i<25;i++){v.applyHairScreenDrag(4,0);tick();hair.forEach((j,n)=>response=Math.max(response,before[n].angleTo(j.bone.quaternion)));}
    const settingsPreserved=all.every((j,n)=>JSON.stringify(j.settings)===settings[n]);
    v.setPhysicsStrength(0);const off=hair.map(j=>j._prevTail.clone());v.applyHairScreenDrag(20,0);
    const offIgnores=hair.every((j,n)=>j._prevTail.equals(off[n]));
    out.push({path:model.path,joints:all.length,hair:hair.length,response,otherIsolated,settingsPreserved,offIgnores,
     finite:all.every(j=>j._prevTail.toArray().concat(j.bone.quaternion.toArray()).every(Number.isFinite))});
   }return out;
  });
  console.log(JSON.stringify(results));assert.deepEqual(errors,[]);
  assert.ok(results.every(r=>r.otherIsolated&&r.settingsPreserved&&r.offIgnores&&r.finite&&(!r.hair||r.response>.001)));
  fs.writeFileSync('audit-results/all-model-hair-2026-10-10/vrm-drag.json',JSON.stringify({results,errors},null,2));
  console.log('PASS: every installed VRM loaded; hair-only drag, preserved spring settings, Off and finite bones');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
