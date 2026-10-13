const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.AUDIT_CHROMIUM,args:['--use-angle=d3d11']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8766/static/physics-check.html');await page.waitForFunction(()=>window.viewer?.physics);
  const results=await page.evaluate(async()=>{
   const THREE=await import('three'),v=window.viewer;v.animate=()=>{};await new Promise(r=>setTimeout(r,50));
   // Synthetic pointer events have no OS capture; disconnect OrbitControls'
   // capture handler while retaining the viewer's real drag listeners.
   v.controls.disconnect();
   const out=[];
   for(const path of ['pmx/Ananta/Taffy/Taffy.pmx','pmx/Ananta/Ringo/Ringo.pmx','pmx/genshin impact/barbara/芭芭拉/芭芭拉.pmx']){
    await v.loadModel('/models/'+path.split('/').map(encodeURIComponent).join('/'));
    v.physicsBoost=0;v.setActivity('idle');v.setPhysicsStrength(1);v.setWindStrength(0);
    for(let i=0;i<650;i++){v._animateCharacter(1/65,i/65);v.physics.update(1/65);}
    const bullet=v.physics.bullet,initial=v.physics.nodes.map(n=>n.bone.quaternion.clone());
    let hairImpulses=0,otherImpulses=0,response=0;
    for(const rigid of bullet.engine.bodies){
     const original=rigid.body.applyCentralImpulse.bind(rigid.body);
     rigid.body.applyCentralImpulse=impulse=>{
      if(bullet.hairBones.has(rigid.bone))hairImpulses++;else otherImpulses++;
      return original(impulse);
     };
    }
    // Real canvas gesture, followed by the native flower/window drag event.
    v.controls.mouseButtons.LEFT=THREE.MOUSE.PAN;
    const canvas=v.renderer.domElement;
    canvas.dispatchEvent(new PointerEvent('pointerdown',{pointerId:7,button:0,clientX:100,clientY:100}));
    canvas.dispatchEvent(new PointerEvent('pointermove',{pointerId:7,buttons:1,clientX:115,clientY:100}));
    canvas.dispatchEvent(new PointerEvent('pointerup',{pointerId:7,button:0,clientX:115,clientY:100}));
    v.physics.update(1/65);const canvasWorks=hairImpulses>0;
    const beforeNative=hairImpulses;
    for(let i=0;i<25;i++){
     window.dispatchEvent(new CustomEvent('sakura-window-drag',{detail:{dx:4,dy:0}}));
     v._animateCharacter(1/65,11+i/65);v.physics.update(1/65);
     v.physics.nodes.forEach((n,j)=>{if(n.category==='hair')response=Math.max(response,initial[j].angleTo(n.bone.quaternion));});
    }
    const nativeWorks=hairImpulses>beforeNative,wakes=bullet.idleTime<3;
    for(let i=0;i<650;i++){v._animateCharacter(1/65,12+i/65);v.physics.update(1/65);}
    const settles=bullet.idleTime>=3;
    v.setPhysicsStrength(0);const beforeOff=hairImpulses;
    v.applyHairScreenDrag(30,20);v.physics.update(1/65);
    const offIgnores=hairImpulses===beforeOff;
    out.push({path,canvasWorks,nativeWorks,hairImpulses,otherImpulses,response,wakes,settles,offIgnores,
     finite:v.model.skeleton.bones.every(b=>b.position.toArray().concat(b.quaternion.toArray()).every(Number.isFinite))});
   }return out;
  });
  console.log(JSON.stringify(results));assert.deepEqual(errors,[]);
  assert.ok(results.every(r=>r.canvasWorks&&r.nativeWorks&&r.hairImpulses>0&&r.otherImpulses===0&&r.response>.001&&r.wakes&&r.settles&&r.offIgnores&&r.finite));
  fs.mkdirSync('audit-results/hair-drag',{recursive:true});fs.writeFileSync('audit-results/hair-drag/results.json',JSON.stringify({results,errors},null,2));
  console.log('PASS: canvas and window drag move hair only; zero wind, idle wake/settle, Off and model switching');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
