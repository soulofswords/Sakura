const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.AUDIT_CHROMIUM,args:['--use-angle=d3d11']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8766/static/physics-check.html');await page.waitForFunction(()=>window.viewer?.physics);
  const result=await page.evaluate(async()=>{
   const viewer=window.viewer;
   await viewer.loadModel('/models/pmx/Ananta/Ringo/Ringo.pmx');
   viewer.animate=()=>{};await new Promise(resolve=>setTimeout(resolve,80));
   const physics=viewer.physics,bullet=physics.bullet,bones=bullet.mesh.skeleton.bones,cases=[];
   const sourceJoints=JSON.stringify(bullet.mesh.geometry.userData.MMD.constraints);
   for(const strength of [.05,.5,1,1.5]){
    physics.setStrength(0);physics.setStrength(strength);
    const original=bullet.rest.map(entry=>entry.position.clone());
    for(let frame=0;frame<180;frame++){viewer._animateCharacter(1/60,frame/60);physics.update(1/60);}
    let worstPosition=0;
    for(let i=0;i<bones.length;i++)worstPosition=Math.max(worstPosition,bones[i].position.distanceTo(original[i]));
    cases.push({strength,gravity:bullet.engine.world.getGravity().y(),worstPosition,
     finite:bones.every(bone=>bone.position.toArray().concat(bone.quaternion.toArray()).every(Number.isFinite))});
   }
   const windTests=[];
   const THREE=await import('three');
   for(const wind of [0,.4]) {
    // Fresh loads isolate wind response from the prior strength test poses.
    await viewer.loadModel('/models/pmx/Ananta/Ringo/Ringo.pmx');
    viewer.setPhysicsStrength(.85);viewer.setWindStrength(wind);
    for(let i=0;i<390;i++)viewer.physics.update(1/65);
    viewer.model.updateMatrixWorld(true);
    const nodes=viewer.physics.nodes,start=nodes.map(n=>n.bone.getWorldPosition(new THREE.Vector3()));
    const swings={hair:0,skirt:0};
    for(let i=0;i<260;i++){
     viewer.physics.update(1/65);viewer.model.updateMatrixWorld(true);
     nodes.forEach((n,j)=>swings[n.category]=Math.max(swings[n.category]||0,start[j].distanceTo(n.bone.getWorldPosition(new THREE.Vector3()))));
    }
    windTests.push({wind,swings});
   }
   const activeBones=viewer.physics.bullet.mesh.skeleton.bones;
   physics.setStrength(0);const parked=activeBones.map(bone=>bone.position.clone());physics.update(1);
   const offStable=activeBones.every((bone,i)=>bone.position.equals(parked[i]));
   await viewer.loadModel('/models/pmx/Ananta/Ringo/Ringo.pmx');
   viewer.setPhysicsStrength(1);viewer.setWindStrength(0);viewer.setUserTracking(true);
   const trackingNodes=viewer.physics.nodes,previous=trackingNodes.map(node=>node.bone.quaternion.clone());
   let fallbackFrame=null,maxSpringStep=0;
   for(let frame=0;frame<360;frame++){
    const t=frame/60,yaw=Math.sin(t*1.7)*.45,roll=Math.sin(t*.9)*.18;
    const faceMatrix=new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(0,yaw,roll));
    viewer.updateUserTracking({face:{matrix:faceMatrix.toArray(),landmarks:[{},{}],blendshapes:[]},hands:[]});
    viewer._animateCharacter(1/60,t);viewer.physics.update(1/60);viewer.model.updateMatrixWorld(true);
    if(viewer.physics.info.engine==='spring fallback'&&fallbackFrame===null)fallbackFrame=frame;
    if(fallbackFrame!==null&&frame>fallbackFrame)for(let i=0;i<trackingNodes.length;i++)
     maxSpringStep=Math.max(maxSpringStep,previous[i].angleTo(trackingNodes[i].bone.quaternion));
    for(let i=0;i<trackingNodes.length;i++)previous[i].copy(trackingNodes[i].bone.quaternion);
   }
   const trackingGuard={engine:viewer.physics.info.engine,warning:viewer.physics.info.warning||null,fallbackFrame,maxSpringStep};
   viewer.setUserTracking(false);
   return {info:physics.info,cases,offStable,
    windTests,rigUnchanged:sourceJoints===JSON.stringify(bullet.mesh.geometry.userData.MMD.constraints),trackingGuard};
  });
  assert.deepEqual(errors,[]);assert.ok(result.cases.every(c=>c.finite&&Math.abs(c.gravity+98)<.001));
  assert.ok(result.info.categories.hair>0&&result.info.categories.skirt>0);
  assert.ok(result.offStable&&result.rigUnchanged);
  assert.equal(result.trackingGuard.engine,'spring fallback','Ringo tracking-induced skirt jumps should automatically use the safe solver');
  assert.ok(result.trackingGuard.fallbackFrame!==null&&result.trackingGuard.maxSpringStep<.2,
   'Fallback should occur after repeated rig spikes and keep subsequent motion smooth');
  assert.ok(result.windTests[1].swings.skirt > result.windTests[0].swings.skirt*2 && result.windTests[1].swings.skirt > .25,
   '40% wind must produce visible skirt movement, beyond no-wind settling');
  fs.mkdirSync('audit-results/ringo-physics',{recursive:true});
  fs.writeFileSync('audit-results/ringo-physics/after.json',JSON.stringify({result,errors},null,2));
  console.log(JSON.stringify(result));console.log('PASS: Ringo low/high strength retains gravity, finite bones, hair/skirt labels, Off stability and authored joint limits');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
