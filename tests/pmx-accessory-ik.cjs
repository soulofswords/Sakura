// Verify the reported real rig, including target convergence and stable repeats.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage();
  await page.goto('http://127.0.0.1:8796/static/library-audit.html?no-capture');
  await page.waitForFunction(()=>window.auditReady,{polling:100,timeout:60000});
  const result=await page.evaluate(async()=>{
   const v=window.auditViewer;cancelAnimationFrame(v.animationFrame);v.animate=()=>{};
   await v.loadModel('/models/'+encodeURI('pmx/NTE/Esper zero - male/男 异能者·零.pmx'));
   const {updateAccessoryIK}=await import('/static/js/pmx-accessory-ik.js');
   const {Vector3}=await import('three');
   const b=v.model.skeleton.bones,iks=v._accessoryIK.iks;
   function errors(){v.model.updateMatrixWorld(true);return iks.map(ik=>b[ik.target].getWorldPosition(new Vector3()).distanceTo(b[ik.effector].getWorldPosition(new Vector3())))}
   for(const ik of iks)for(const link of ik.links)b[link.index].quaternion.identity();
   const before=errors();updateAccessoryIK(v);const after=errors();
   const q=iks.flatMap(ik=>ik.links.map(l=>b[l.index].quaternion.clone()));
   for(let i=0;i<200;i++)updateAccessoryIK(v);
   const drift=Math.max(...iks.flatMap(ik=>ik.links.map(l=>b[l.index].quaternion.angleTo(q.shift()))));
   for(let i=0;i<12;i++){v._renderFrame();await new Promise(resolve=>setTimeout(resolve,20));}
   const frameErrors=errors();
   return {before,after,frameErrors,drift,chains:iks.length,mainBonesTouched:iks.some(ik=>ik.links.some(l=>Object.values(v.animationBones).some(x=>x.bone===b[l.index])))};
  });
  assert.equal(result.chains,2);assert.equal(result.mainBonesTouched,false);
  for(let i=0;i<2;i++)assert.ok(result.after[i]<result.before[i]*.05,JSON.stringify(result));
  for(let i=0;i<2;i++)assert.ok(result.frameErrors[i]<result.before[i]*.08,JSON.stringify(result));
  assert.ok(result.drift<.001,JSON.stringify(result));
  console.log('PASS: Esper Zero sleeve IK follows lowered arms, does not touch main body IK, no cumulative drift.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
