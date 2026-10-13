const assert=require('node:assert/strict'),fs=require('node:fs');const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=d3d11']});try{const p=await b.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto('http://127.0.0.1:8766/static/physics-check.html');await p.waitForFunction(()=>window.viewer?.physics);const r=await p.evaluate(async()=>{
 const v=window.viewer;await v.loadModel('/models/pmx/Ananta/Ringo/Ringo.pmx');
 let empty=0,loadingDraws=0,draws=0,reallocations=0;const render=v.renderer.render.bind(v.renderer),resize=v.renderer.setDrawingBufferSize.bind(v.renderer);
 v.renderer.render=(...a)=>{draws++;if(v._displayLoading)loadingDraws++;if(!v.model)empty++;return render(...a);};
 v.renderer.setDrawingBufferSize=(...a)=>{reallocations++;return resize(...a);};
 const lights=[];for(const q of ['low','high','balanced','balanced','high']){v.setQuality(q);lights.push([v.ambientLight.intensity,v.keyLight.intensity,v.fillLight.intensity]);}
 const before=reallocations;v.setQuality('high');const idempotent=before===reallocations;
 const next=v.loadModel('/models/pmx/Ananta/Taffy/Taffy.pmx');v.setQuality('low');await next;
 let rejected=false;try{await v.loadModel('/models/definitely-missing.pmx');}catch(_){rejected=true;}
 const unlocked=!v._displayLoading;await v.loadModel('/models/pmx/Ananta/Ringo/Ringo.pmx');
 return {empty,loadingDraws,draws,idempotent,lights,rejected,unlocked,quality:v.quality,model:!!v.model};
 });assert.deepEqual(errors,[]);assert.equal(r.loadingDraws,0);assert.ok(r.idempotent&&r.rejected&&r.unlocked&&r.model);assert.ok(r.lights.every(x=>JSON.stringify(x)===JSON.stringify(r.lights[0])));assert.equal(r.quality,'low');fs.mkdirSync('audit-results/presentation',{recursive:true});fs.writeFileSync('audit-results/presentation/results.json',JSON.stringify({r,errors},null,2));console.log(JSON.stringify(r));console.log('PASS: quality redraw, idempotent resizing, deferred settings, load frame hold, failure unlock and recovery');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
