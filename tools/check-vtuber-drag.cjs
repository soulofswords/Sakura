const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=d3d11']});
 try {
 const page=await browser.newPage({viewport:{width:900,height:700}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8766/static/physics-check.html?library=1&upload=1');
 await page.waitForFunction(()=>window.viewer?.physics);
 await page.evaluate(async()=>{
  const v=window.viewer;v.animate=()=>{};await new Promise(r=>setTimeout(r,50));
  await v.loadModel('/models/pmx/Ananta/Ringo/Ringo.pmx');
  v.setVtuberTrackingMode(true);v.setUserTracking(true);v.setPhysicsStrength(1);v.setWindStrength(0);
  for(let i=0;i<240;i++){v._animateCharacter(1/60,i/60);v.physics.update(1/60);}
  window.dragBefore=v.physics.nodes.map(n=>n.bone.quaternion.clone());window.dragCalls=0;
  const original=v.physics.applyCharacterDrag.bind(v.physics);
  v.physics.applyCharacterDrag=d=>{window.dragCalls++;original(d);};
 });
 await page.mouse.move(350,220);await page.mouse.down();await page.mouse.move(470,260,{steps:8});await page.mouse.up();
 const result=await page.evaluate(async()=>{
  const v=window.viewer,THREE=await import('three');
  for(let i=0;i<10;i++){v._animateCharacter(1/60,i/60);v.physics.update(1/60);}
  const hair=Math.max(0,...v.physics.nodes.map((n,i)=>n.category==='hair'?dragBefore[i].angleTo(n.bone.quaternion):0));
  const pan=v.controls.mouseButtons.LEFT===THREE.MOUSE.PAN;
  v.setVtuberTrackingMode(false);const restored=v.controls.mouseButtons.LEFT===THREE.MOUSE.ROTATE;
  return {calls:window.dragCalls,hair,pan,restored,tracking:v.userTracking,finite:v.physics.nodes.every(n=>n.bone.quaternion.toArray().every(Number.isFinite))};
 });
 assert.deepEqual(errors,[]);assert.ok(result.calls>0&&result.hair>.0001&&result.pan&&result.restored&&result.tracking&&result.finite);
 fs.mkdirSync('audit-results/drag-speech',{recursive:true});fs.writeFileSync('audit-results/drag-speech/vtuber-pointer.json',JSON.stringify({result,errors},null,2));
 console.log(JSON.stringify(result));console.log('PASS: real left-pointer drag in VTuber library view moves physics while retargeting runs; AI controls restored');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
