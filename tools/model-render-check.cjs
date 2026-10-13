// Private browser, fresh pages, no screenshots, no shared browser profile.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {chromium}=require('playwright');
const base=process.env.SAKURA_AUDIT_URL,root=process.cwd(),output=process.env.SAKURA_AUDIT_RESULT;
const state={models:[],live2d:[],complete:false};
const save=()=>{fs.writeFileSync(output+'.tmp',JSON.stringify(state,null,2));fs.renameSync(output+'.tmp',output);};
const parserContext=vm.createContext({console,TextDecoder});
vm.runInContext(fs.readFileSync('static/vendor/three/examples/jsm/libs/mmdparser.module.js','utf8')
 .replace('export { MMDParser, CharsetEncoder, Parser };','globalThis.Parser=Parser;'),parserContext);
function parsePmx(modelPath){
 const file=path.join(root,'models',modelPath),data=fs.readFileSync(file);
 const model=new parserContext.Parser().parsePmx(data.buffer.slice(data.byteOffset,data.byteOffset+data.byteLength),true);
 return {vertices:model.vertices.length,triangles:model.faces.length,
  badVertices:model.vertices.filter(v=>!v.position.every(Number.isFinite)).length,
  badFaces:model.faces.filter(f=>f.indices.some(i=>i<0||i>=model.vertices.length)).length};
}
(async()=>{
 const response=await fetch(base+'/api/models');if(!response.ok)throw Error('Catalog request failed');
 const catalog=await response.json();let models=catalog.models;
 if(process.env.SAKURA_AUDIT_FILTER)models=models.filter(m=>m.path.toLowerCase().includes(process.env.SAKURA_AUDIT_FILTER.toLowerCase()));
 if(process.env.SAKURA_AUDIT_SAMPLE==='1'){
  const pmx=models.filter(m=>/\.pmx$/i.test(m.path)),vrm=models.filter(m=>/\.vrm$/i.test(m.path));
  models=[pmx[0],pmx.at(-1),vrm[0]].filter((m,i,a)=>m&&a.findIndex(n=>n?.path===m.path)===i);
 }
 const limit=Number(process.env.SAKURA_AUDIT_LIMIT||0);if(limit)models=models.slice(0,limit);
 state.total=models.length;state.libraryTotal=catalog.models.length;
 state.live2d=catalog.live2d_models.map(m=>({...m,status:'Live2D runtime supported; not included in this PMX/VRM audit.'}));save();
 if(!models.length)throw Error('No PMX/VRM models match this check.');
 const browser=await chromium.launch({headless:true,executablePath:process.env.SAKURA_AUDIT_BROWSER,
  args:['--enable-webgl','--use-angle=d3d11','--disable-background-timer-throttling']});
 let context,page,errors=[],warnings=[],missing=[],used=0;
 async function fresh(){
  if(context)await context.close();
  context=await browser.newContext({viewport:{width:320,height:440},deviceScaleFactor:1,serviceWorkers:'block'});
  page=await context.newPage();
  page.on('pageerror',error=>errors.push(error.message));
  page.on('console',message=>{
   // Optional textures.json requests can legitimately return 404. Actual asset
   // failures are tracked from responses; don't count Chrome's generic 404 line twice.
   if(message.type()==='error'&&!message.text().startsWith('Failed to load resource:'))errors.push(message.text());
   else if(message.type()==='warning')warnings.push(message.text());
  });
  page.on('response',response=>{
   const headers=response.headers();
   if(headers['x-sakura-asset-fallback']==='missing'||(response.status()>=400&&!response.url().endsWith('/textures.json')))
    missing.push({url:response.url(),status:response.status(),fallback:headers['x-sakura-asset-fallback']||null});
  });
  errors=[];warnings=[];missing=[];
  await page.goto(base+'/audit.html?no-capture',{timeout:30000});
  await page.waitForFunction(()=>window.auditReady,{timeout:30000});used=0;
 }
 try {
  for(const model of models){
   errors=[];warnings=[];missing=[];let result;const start=Date.now();
   try {
    const geometry=/\.pmx$/i.test(model.path)?parsePmx(model.path):null;
    if(geometry&&(geometry.badVertices||geometry.badFaces))throw Error('Invalid PMX vertices/triangle indices: '+JSON.stringify(geometry));
    if(!page||used>=6)await fresh();
    errors=[];warnings=[];missing=[];
    let timer;
    try {
     result=await Promise.race([page.evaluate(async modelPath=>{
      const result=await window.auditModel(modelPath);delete result.desktopPreview;
      const viewer=window.auditViewer;
      let finite=true,bones=0;
      // Sample natural, wind-free physics without talking or procedural gestures.
      viewer.setActivity('idle');viewer.physicsBoost=0;viewer.setWindStrength(0);
      for(let i=0;i<90;i++){
       viewer.physics?.update(1/60);if(viewer.vrm)viewer.vrm.update(1/60);
      }
      viewer.model?.traverse(node=>{if(node.isBone){bones++;finite=finite&&node.position.toArray().concat(node.quaternion.toArray(),node.scale.toArray()).every(Number.isFinite);}});
      viewer._renderFrame();const gl=viewer.renderer.getContext();
      return {...result,bones,finite,physicsInfo:viewer.physics?.info||null,
       contextLost:gl.isContextLost(),glError:gl.getError(),renderer:gl.getParameter(gl.RENDERER)};
     },model.path),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Model load/render timeout (90 seconds)')),90000);})]);
    }finally{clearTimeout(timer);}
    result.geometry=geometry;used++;
    result.ok=!!result.ok&&result.visiblePixels>20&&result.desktopVisiblePixels>20&&result.finite&&result.bounds.min.concat(result.bounds.max).every(Number.isFinite)&&!result.contextLost&&result.glError===0&&!errors.length;
    if(!result.ok&&!result.error)result.error=errors[0]||'Blank frame, invalid bone transforms, or WebGL failure';
   }catch(error){result={ok:false,error:String(error)};if(context)await context.close().catch(()=>{});context=null;page=null;}
   state.models.push({path:model.path,...result,seconds:+((Date.now()-start)/1000).toFixed(2),errors:[...new Set(errors)],warnings:[...new Set(warnings)],missingTextures:missing});
   save();console.log(JSON.stringify({checked:state.models.length,total:state.total,path:model.path,ok:result.ok,missing:missing.length}));
  }
  state.complete=true;save();
 }finally{await browser.close();}
 process.exitCode=state.models.some(m=>!m.ok)?2:0;
})().catch(error=>{state.fatal=String(error);save();console.error(error);process.exitCode=1;});
