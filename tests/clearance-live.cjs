const fs=require('node:fs'),assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.AUDIT_CHROMIUM,args:['--use-angle=d3d11']});
 try{
  const page=await browser.newPage({viewport:{width:480,height:640}});const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8766/static/library-audit.html');await page.waitForFunction(()=>window.auditReady);
  const paths=['pmx/Miku universe/Miku/TDA Miku Uniform/TDA Miku Uniform.pmx','pmx/Ananta/Taffy/Taffy.pmx'];
  const list=await page.evaluate(async()=> (await(await fetch('/api/models')).json()).models);
  paths.push(list.find(m=>m.path.toLowerCase().includes('barbara'))?.path);
  paths.push(list.find(m=>m.path.toLowerCase().endsWith('.vrm'))?.path);
  const results=[];
  fs.mkdirSync('audit-results/clearance',{recursive:true});
  for(const path of paths.filter(Boolean)){
   const result=await page.evaluate(async path=>{
    const v=window.auditViewer;v.setQuality('low');
    await v.loadModel('/models/'+path.split('/').map(encodeURIComponent).join('/'));
    v.physics.setMode('off');v.setActivity('talking');v.setSpeechLevel(.8);
    const original=v._avoidArmClipping;v._avoidArmClipping=()=>{};
    const before=[],after=[],cost=[];
    try{
     for(let i=0;i<240;i++){
      v._animateCharacter(1/30,i/30);v.model.updateMatrixWorld(true);
      if(v.vrm){v.vrm.update(0);v.model.updateMatrixWorld(true);}
      if(!v.armClearance || v.armClearance.root!==v.model) original.call(v);
      const guard=v.armClearance;
      guard.inverse.copy(v.model.matrixWorld).invert();
      before.push(Math.max(0,...guard.arms.map(a=>guard.penetration(a))));
      const start=performance.now();guard.update();cost.push(performance.now()-start);
      after.push(guard.metrics.after);
     }
    }finally{v._avoidArmClipping=original;}
    let finite=true;v.model.traverse(b=>{if(b.isBone)finite&&=[...b.position.toArray(),...b.quaternion.toArray()].every(Number.isFinite);});
    const mean=a=>a.reduce((s,n)=>s+n,0)/a.length;
    return {path,finite,arms:v.armClearance.arms.length,bands:!!v.armClearance.bands,meanBefore:mean(before),meanAfter:mean(after),worstBefore:Math.max(...before),worstAfter:Math.max(...after),meanMs:mean(cost),maxMs:Math.max(...cost)};
   },path);
   results.push(result);
   assert.ok(result.finite&&result.bands&&result.arms===2,path+' has usable clearance');
   assert.ok(result.meanAfter<=result.meanBefore+.015,path+' reduces average overlap');
   await page.evaluate(()=>{const v=window.auditViewer;v.fullModelView=true;v._autoFrame(v.model);v._renderFrame();});
   await page.screenshot({path:'audit-results/clearance/preview-'+results.length+'.png'});
  }
  assert.deepEqual(errors,[]);
  fs.writeFileSync('audit-results/clearance/results.json',JSON.stringify({results,errors},null,2));console.log(JSON.stringify(results));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
