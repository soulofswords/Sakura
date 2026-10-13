const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=d3d11']});
 try{
 const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8766/static/physics-check.html');await page.waitForFunction(()=>window.viewer?.physics);
 const results=await page.evaluate(async()=>{
  const v=window.viewer;v.animate=()=>{};await new Promise(r=>setTimeout(r,50));
  const models=(await(await fetch('/api/models')).json()).models;
  const paths=['Ananta/Taffy/','Ananta/Ringo/','Dr. Ratio/'];const out=[];
  for(const term of paths){
   const m=models.find(m=>m.path.includes(term)&&m.path.endsWith('.pmx'));if(!m)throw Error('Missing '+term);
   await v.loadModel('/models/'+m.path.split('/').map(encodeURIComponent).join('/'));
   v.setPhysicsStrength(1);v.setWindStrength(0);
   for(let i=0;i<240;i++)v.physics.update(1/60);
   const baseline=v.physics.nodes.map(n=>n.bone.quaternion.clone());
   v.applyHairScreenDrag(80,-20);
   for(let i=0;i<10;i++)v.physics.update(1/60);
   const categories={};v.physics.nodes.forEach((n,i)=>categories[n.category]=Math.max(categories[n.category]||0,baseline[i].angleTo(n.bone.quaternion)));
   for(let i=0;i<240;i++)v.physics.update(1/60);
   const breast=v.physics.nodes.filter(n=>n.category==='breast'),before=breast.map(n=>n.bone.quaternion.clone());
   for(let i=0;i<45;i++){v.physics.updateSpeechPhysics(i%12<6?.9:.1,1/60);v.physics.update(1/60);}
   const speech=Math.max(0,...breast.map((n,i)=>before[i].angleTo(n.bone.quaternion)));
   const finite=v.physics.nodes.every(n=>n.bone.quaternion.toArray().every(Number.isFinite));
   out.push({path:m.path,bones:v.physics.nodes.length,categories,breastBones:breast.length,speech,finite});
  }return out;
 });
 assert.deepEqual(errors,[]);assert.ok(results.every(r=>r.finite&&Math.max(...Object.values(r.categories))>.0001));
 assert.ok(results.some(r=>r.breastBones>0&&r.speech>.00001));
 fs.mkdirSync('audit-results/drag-speech',{recursive:true});fs.writeFileSync('audit-results/drag-speech/results.json',JSON.stringify({results,errors},null,2));
 console.log(JSON.stringify(results));console.log('PASS: actual PMX drag response, speech chest response and stability in private renderer');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
