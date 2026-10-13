const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.AUDIT_CHROMIUM,args:['--use-angle=d3d11']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8766/static/physics-check.html');await page.waitForFunction(()=>window.viewer?.physics);
  const results=await page.evaluate(async()=>{
   const THREE=await import('three'),v=window.viewer;v.animate=()=>{};await new Promise(r=>setTimeout(r,50));
   const paths=['pmx/Ananta/Taffy/Taffy.pmx','pmx/Ananta/Ringo/Ringo.pmx','pmx/genshin impact/barbara/芭芭拉/芭芭拉.pmx'],out=[];
   for(const path of paths){
    await v.loadModel('/models/'+path.split('/').map(encodeURIComponent).join('/'));
    v.physicsBoost=0;v.setActivity('idle');v.setPhysicsStrength(1);v.setWindStrength(0);
    for(let i=0;i<650;i++){v._animateCharacter(1/65,i/65);v.physics.update(1/65);}
    v.model.updateMatrixWorld(true);
    const initial=v.physics.nodes.map(n=>n.bone.getWorldPosition(new THREE.Vector3()));let drift=0;
    for(let i=0;i<260;i++){
     v._animateCharacter(1/65,(650+i)/65);v.physics.update(1/65);v.model.updateMatrixWorld(true);
     v.physics.nodes.forEach((n,j)=>drift=Math.max(drift,initial[j].distanceTo(n.bone.getWorldPosition(new THREE.Vector3()))));
    }
    const sleeping=v.physics.bullet.idleTime>=3;
    v.setActivity('talking');v._animateCharacter(1/65,15);v.physics.update(1/65);
    const talkWakes=v.physics.bullet.idleTime===0;
    v.setActivity('idle');v.setWindStrength(.4);v.physics.update(1/65);
    const windWakes=v.physics.bullet.idleTime===0;
    v.setWindStrength(0);
    // Resting physics must wake even for external tracking/manual bone changes.
    v.physics.allowIdleSleep=true;v.physics.bullet.idleTime=4;
    v.animationBones.head.bone.rotation.z+=.1;v.physics.update(1/65);
    const anchorWakes=v.physics.bullet.idleTime===0;
    out.push({path,drift,sleeping,talkWakes,windWakes,anchorWakes,
     finite:v.physics.bullet.mesh.skeleton.bones.every(b=>b.position.toArray().concat(b.quaternion.toArray()).every(Number.isFinite))});
   }return out;
  });
  console.log(JSON.stringify(results));assert.deepEqual(errors,[]);
  assert.ok(results.every(r=>r.drift<.002&&r.sleeping&&r.talkWakes&&r.windWakes&&r.anchorWakes&&r.finite));
  fs.mkdirSync('audit-results/physics-idle',{recursive:true});
  fs.writeFileSync('audit-results/physics-idle/results.json',JSON.stringify({results,errors},null,2));
  console.log('PASS: hidden Taffy/Ringo/Barbara settle without idle jitter; gestures, wind and anchor movement wake physics');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
