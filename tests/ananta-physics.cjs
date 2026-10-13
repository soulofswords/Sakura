// Private headless stability check for the four Ananta PMX physics rigs.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');

(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.AUDIT_CHROMIUM||'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--enable-webgl','--use-angle=d3d11']});
 try{
  const page=await browser.newPage({viewport:{width:900,height:700}}),errors=[];
  page.on('pageerror',error=>errors.push(String(error)));
  await page.goto('http://127.0.0.1:8766/static/physics-check.html');
  await page.waitForFunction(()=>window.viewer?.physics);
  const report=await page.evaluate(async()=>{
   const viewer=window.viewer;viewer.animate=()=>{};viewer.controls.disconnect();
   const paths=['Mechanika/Mechanika.pmx','Richie/Richie.pmx','Ringo/Ringo.pmx','Taffy/Taffy.pmx'];
   const results=[];
   for(const file of paths){
    const path='/models/pmx/Ananta/'+file;
    const previous=viewer.physics;
    if(results.length)previous.glitchFixEnabled=true;
    const loaded=await viewer.loadModel(path);if(!loaded)throw Error('Model failed to load: '+file);
    const physics=viewer.physics,mesh=physics.bullet?.mesh;
    const before=physics.info.bones,source=mesh?JSON.stringify(mesh.geometry.userData.MMD):null;
    const candidateCount=physics.info.glitch?.detected??0;
    viewer.setGlitchFix(true);
    const afterEnable=physics.info.bones,active=physics.info.glitch?.active??false;
    viewer.setGlitchFix(false);
    const afterRestore=physics.info.bones;
    viewer.setPhysicsStrength(1);viewer.setWindStrength(0);
    const bones=[];viewer.model.traverse(object=>{if(object.isBone)bones.push(object);});
    const initial=bones.map(bone=>({p:bone.position.clone(),q:bone.quaternion.clone()}));
    let maxTravel=0,finite=true;
    for(let frame=0;frame<240;frame++){
     viewer.model.position.x=Math.sin(frame/17)*.35;
     viewer.model.updateMatrixWorld(true);physics.update(1/60);viewer.model.updateMatrixWorld(true);
     for(let i=0;i<bones.length;i++){
      const bone=bones[i];finite&&=bone.position.toArray().concat(bone.quaternion.toArray()).every(Number.isFinite);
      maxTravel=Math.max(maxTravel,bone.position.distanceTo(initial[i].p));
     }
    }
    const rigUnchanged=!mesh||source===JSON.stringify(mesh.geometry.userData.MMD);
    results.push({file,engine:physics.info.engine,bones:before,chains:physics.info.chains,
     hair:physics.info.categories?.hair||0,skirt:physics.info.categories?.skirt||0,
     cleanupCandidates:candidateCount,afterEnable,active,afterRestore,maxTravel:+maxTravel.toFixed(4),finite,rigUnchanged});
    if(results.length>1)results.at(-1).previousModelCleanupReset=previous.glitchFixEnabled===false;
   }
   return results;
  });
  assert.deepEqual(errors,[]);
  for(const result of report){
   assert.equal(result.engine,'Bullet',result.file+' did not use the PMX rig solver');
   assert.ok(result.bones>0&&result.chains>0,result.file+' has no active rig');
   assert.equal(result.cleanupCandidates,0,result.file+' has no structurally duplicate pivots to exclude');
   assert.equal(result.afterEnable,result.bones,result.file+' lost distinct chains');
   assert.equal(result.afterRestore,result.bones,result.file+' did not restore its chain count');
   assert.equal(result.active,false,result.file+' incorrectly enabled cleanup without candidates');
   assert.ok(result.finite&&result.rigUnchanged,result.file+' corrupted a transform or authored rig metadata');
   assert.ok(result.maxTravel<5,result.file+' physics became unstable');
   if(report.indexOf(result)>0)assert.equal(result.previousModelCleanupReset,true,result.file+' inherited the previous model cleanup flag');
  }
  fs.mkdirSync('audit-results/ananta-physics',{recursive:true});
  fs.writeFileSync('audit-results/ananta-physics/results.json',JSON.stringify({models:report,errors},null,2));
  console.log(JSON.stringify(report));
  console.log('PASS: Ananta Bullet rigs remain finite, stable, structurally intact and fully restored after cleanup toggles');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
