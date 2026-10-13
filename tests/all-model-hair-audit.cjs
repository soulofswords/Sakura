// Headless library-wide loading/physics audit. Never opens the companion UI.
const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const output='audit-results/all-model-hair-2026-10-10';
fs.mkdirSync(output,{recursive:true});
const baseFile=path.join(output,'results.json');
const worker=process.env.AUDIT_WORKER;
const file=worker===undefined?baseFile:path.join(output,`results-worker-${worker}.json`);
const previous=worker!==undefined&&fs.existsSync(baseFile)?JSON.parse(fs.readFileSync(baseFile,'utf8')).models:[];
const report=fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')):{models:[],live2d:[],complete:false};
const save=()=>fs.writeFileSync(file,JSON.stringify(report,null,2));
(async()=>{
 const inventory=await (await fetch('http://127.0.0.1:8766/api/models')).json();
 report.total=inventory.models.length;report.live2d=inventory.live2d_models;save();
 const browser=await chromium.launch({headless:true,executablePath:process.env.AUDIT_CHROMIUM,args:['--use-angle=d3d11']});
 let page,errors=[],missing=[];
 async function reset(){
  if(page)await page.close().catch(()=>{});
  page=await browser.newPage({viewport:{width:640,height:800}});
  page.on('pageerror',e=>errors.push(String(e)));
  page.on('response',response=>{if(response.status()>=400)missing.push({url:response.url(),status:response.status()});});
  await page.goto('http://127.0.0.1:8766/static/physics-check.html');
  await page.waitForFunction(()=>window.viewer?.physics);
  await page.evaluate(async()=>{
   const v=window.viewer;v.animate=()=>{};v.controls.disconnect();
   v.setQuality('balanced');v.setCharacterGlow(0);v.setGlossBoost(0);
   await new Promise(resolve=>setTimeout(resolve,50));
  });
 }
 try{
  const done=new Set([...previous,...report.models].map(m=>m.path));let batch=0;
  for(const [index,model] of inventory.models.entries()){
   if(worker!==undefined && index%Number(process.env.AUDIT_WORKERS||2)!==Number(worker))continue;
   if(done.has(model.path))continue;
   if(!page||batch>=12){await reset();batch=0;}
   errors=[];missing=[];const start=Date.now();let result;
   try{
    result=await Promise.race([page.evaluate(async modelPath=>{
     const THREE=await import('three'),v=window.viewer;
     const loaded=await v.loadModel('/models/'+modelPath.split('/').map(encodeURIComponent).join('/'));
     if(!loaded||!v.model)throw Error('Model returned no renderable object');
     v.physicsBoost=0;v.setActivity('idle');v.setPhysicsStrength(1);v.setWindStrength(0);
     const tick=()=>{v._animateCharacter(1/65,0);v.physics.update(1/65);if(v.vrm)v.vrm.update(1/65);};
     for(let i=0;i<260;i++)tick();
     const nodes=v.physics.nodes,hair=nodes.filter(n=>n.category==='hair'),bullet=v.physics.bullet;
     const initial=hair.map(n=>n.bone.quaternion.clone());let impulses=0,otherImpulses=0,response=0;
     if(bullet)for(const rigid of bullet.engine.bodies){
      const apply=rigid.body.applyCentralImpulse.bind(rigid.body);
      rigid.body.applyCentralImpulse=value=>{
       if(bullet.hairBones.has(rigid.bone))impulses++;else otherImpulses++;
       return apply(value);
      };
     }
     const cloth=nodes.filter(n=>n.category!=='hair');
     const clothPrev=cloth.map(n=>n.prev?.clone());
     v.applyHairScreenDrag(10,0);
     const fallbackIsolated=cloth.every((n,i)=>!clothPrev[i]||n.prev.equals(clothPrev[i]));
     for(let i=0;i<25;i++){
      window.dispatchEvent(new CustomEvent('sakura-window-drag',{detail:{dx:4,dy:0}}));tick();
      hair.forEach((n,j)=>response=Math.max(response,initial[j].angleTo(n.bone.quaternion)));
     }
     for(let i=0;i<260;i++)tick();
     const settling=bullet?(!bullet.idleAnchors.length||bullet.idleTime>=3):null;
     const offBefore=impulses;v.setPhysicsStrength(0);v.applyHairScreenDrag(20,10);tick();
     const offIgnores=impulses===offBefore;v.setPhysicsStrength(1);
     let vertices=0,materials=0,bones=0,finite=true;
     v.model.traverse(o=>{
      vertices+=o.geometry?.attributes?.position?.count||0;
      materials+=o.material?(Array.isArray(o.material)?o.material.length:1):0;
      if(o.isBone){bones++;finite&&=o.position.toArray().concat(o.quaternion.toArray()).every(Number.isFinite);}
     });
     v._renderFrame();const gl=v.renderer.getContext();
     const pixels=new Uint8Array(gl.drawingBufferWidth*gl.drawingBufferHeight*4);
     gl.readPixels(0,0,gl.drawingBufferWidth,gl.drawingBufferHeight,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
     let visible=0;for(let i=3;i<pixels.length;i+=4)if(pixels[i]>20)visible++;
     return {loaded:true,vertices,materials,bones,finite,contextLost:gl.isContextLost(),visible,
      engine:v.physics.info?.engine||v.physics.source,physics:v.physics.info,hairBones:hair.length,
      impulses,otherImpulses,response,fallbackIsolated,settling,offIgnores,
      hairStatus:v.vrm?'VRM spring runtime; PMX drag not applied':!hair.length?'No detected hair physics':
       bullet?(impulses>0?'Drag applied to hair rig':'FAILED: no hair impulse'):'Drag applied to fallback hair'};
    },model.path),new Promise((_,reject)=>{const timer=setTimeout(()=>reject(Error('Model audit timeout (90s)')),90000);timer.unref();})]);
   }catch(error){result={loaded:false,error:String(error)};await page.close().catch(()=>{});page=null;}
   report.models.push({path:model.path,...result,seconds:+((Date.now()-start)/1000).toFixed(2),errors:[...errors],missing:[...missing]});
   save();batch++;
   if(report.models.length%10===0||!result.loaded)console.log(JSON.stringify({checked:report.models.length,total:report.total,last:model.path,loaded:result.loaded,failed:report.models.filter(m=>!m.loaded).length}));
  }
  report.complete=true;save();
  console.log(JSON.stringify({complete:true,total:report.total,loaded:report.models.filter(m=>m.loaded).length,
   hairRig:report.models.filter(m=>m.hairBones>0).length,failures:report.models.filter(m=>!m.loaded).map(m=>({path:m.path,error:m.error}))}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);save();process.exitCode=1;});
