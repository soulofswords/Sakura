const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.AUDIT_CHROMIUM,args:['--use-angle=d3d11']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8766/static/physics-check.html');await page.waitForFunction(()=>window.viewer?.physics);
  const source=fs.readFileSync('static/js/app.js','utf8');
  const applySource=source.slice(source.indexOf('function applyPhysicsStrength('),source.indexOf('function updatePhysicsUI('));
  const result=await page.evaluate(async applySource=>{
   const viewer=window.viewer;viewer.animate=()=>{};await new Promise(r=>setTimeout(r,50));
   await viewer.loadModel('/models/pmx/Ananta/Taffy/Taffy.pmx');
   const apply=new Function('viewer','localStorage','updatePhysicsUI',applySource+';applyPhysicsStrength(0,false);');
   viewer.physicsEnabled=true;apply(viewer,localStorage,()=>{});viewer.setWindStrength(0);
   const ph=viewer.physics,hair=ph.nodes.filter(n=>n.category==='hair');
   for(let frame=0;frame<130;frame++)ph.update(1/65);
   const before=hair.map(n=>n.bone.quaternion.clone());
   const head=viewer.animationBones.head.bone,rest=head.rotation.clone();
   head.rotation.z+=.18;viewer.model.updateMatrixWorld(true);
   for(let frame=0;frame<25;frame++)ph.update(1/65);
   head.rotation.copy(rest);viewer.model.updateMatrixWorld(true);ph.update(1/65);
   const response=Math.max(0,...hair.map((n,i)=>before[i].angleTo(n.bone.quaternion)));
   const baseline={mode:ph.mode,strength:ph.strength,wind:ph.windStrength,hairBones:hair.length,response,info:ph.info};
   viewer.physicsEnabled=false;apply(viewer,localStorage,()=>{});const off=ph.mode==='off';
   viewer.physicsEnabled=true;apply(viewer,localStorage,()=>{});
   return {...baseline,off,resumed:ph.mode!=='off'&&ph.strength===1,
    finite:ph.bullet.mesh.skeleton.bones.every(b=>b.position.toArray().concat(b.quaternion.toArray()).every(Number.isFinite))};
  },applySource);
  console.log(JSON.stringify(result));
  assert.deepEqual(errors,[]);assert.equal(result.strength,1);assert.equal(result.wind,0);
  assert.ok(result.hairBones>0&&result.response>.001&&result.finite&&result.off&&result.resumed);
  fs.mkdirSync('audit-results/taffy-natural',{recursive:true});
  fs.writeFileSync('audit-results/taffy-natural/results.json',JSON.stringify({result,errors},null,2));
  console.log(JSON.stringify(result));console.log('PASS: Taffy at 0% boost has active natural hair physics without wind; responds to head movement; separate Off/resume');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
