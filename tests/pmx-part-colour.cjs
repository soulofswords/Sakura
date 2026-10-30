const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage({viewport:{width:700,height:850}}),shaderErrors=[];
  let brokenTextures=false;
  page.on('console',message=>{if(message.type()==='error'&&/Shader Error|VALIDATE_STATUS|shader error/i.test(message.text()))shaderErrors.push(message.text());});
  await page.route('http://pmx.test/**',route=>{
   const url=new URL(route.request().url()),relative=decodeURIComponent(url.pathname).slice(1),file=path.resolve(relative);
   if(!file.startsWith(process.cwd()+path.sep)||!['static','models'].includes(relative.split('/')[0]))return route.fulfill({status:404,body:''});
   // Simulate unreadable artwork; do not depend on corrupt owner files remaining
   // corrupt after they have been recovered from their intact originals.
   if(brokenTextures&&/Gratia_MMD\/tex\/T_GratiaDefault_(Face01|Skin01|Hair01|Hat01|Pupil01|EyeTrans01|Special01)_A_D\.png$/i.test(relative))return route.fulfill({contentType:'image/png',body:Buffer.alloc(32)});
   if(fs.existsSync(file)&&fs.statSync(file).isFile())return route.fulfill({contentType:file.endsWith('.js')?'text/javascript':file.endsWith('.html')?'text/html':'application/octet-stream',body:fs.readFileSync(file)});
   if(relative.startsWith('models/')&&/\.(png|bmp|tga|dds|sph|spa)$/i.test(relative)){
    const color=url.searchParams.get('fallback')==='black'?'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAX+XDSwAAAABJRU5ErkJggg==':'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==';
    return route.fulfill({contentType:'image/png',body:Buffer.from(color,'base64')});
   }
   return route.fulfill({status:404,body:''});
  });
  await page.goto('http://pmx.test/static/library-audit.html?no-capture');await page.waitForFunction(()=>window.auditReady);

  const result=await page.evaluate(async()=>{
   const {ModelMaterials}=await import('/static/js/model-materials.js');
   const loaded=await auditModel('pmx/Richie/Richie.pmx');
   if(!loaded.ok)throw Error('Richie did not load');
   const v=auditViewer,c=new ModelMaterials(v);c.attach('richie');
   const entry=c.entries.find(e=>e.name==='e眼白'),iris=c.entries.find(e=>e.name==='e眼珠');
   if(!entry||!iris)throw Error('Expected eye materials');
   const m=entry.material,source=m.map,other=iris.material.map;
   const uniforms=()=>[m.uniforms.sakuraPmxDiffuse.value.toArray(),m.uniforms.sakuraPmxAmbient.value.toArray()];
   const original=uniforms(),visibility=v.model.material.map(x=>x.visible);
   v.model.material.forEach(x=>x.visible=x===m);
   function pixels(){const f=v.captureTextureDiagnosticFrame(800);let count=0,sum=0;for(let i=0;i<f.pixels.length;i+=4)if(f.pixels[i+3]>240){count++;sum+=f.pixels[i]+f.pixels[i+1]+f.pixels[i+2];}return {count,mean:sum/Math.max(1,count*3)};}
   const before=pixels();
   c.setColor(entry.id,{color:'#ffffff',strength:1,opacity:1});
   const white=pixels(),edited=uniforms(),isolated=iris.material.map===other&&source!==m.map;
   c.setColor(entry.id,null);const reset=pixels(),restored=uniforms(),sameMap=m.map===source;
   c.setColor(entry.id,{color:'#ffffff',strength:0,opacity:.5});const opacityOnly=uniforms();
   c.restore();v.model.material.forEach((x,i)=>x.visible=visibility[i]);
   return {before,white,reset,original,edited,restored,opacityOnly,sameMap,isolated};
  });
  assert.ok(result.before.count>10,JSON.stringify(result));
  // Neutral key fill now makes the original eye white brighter too. The
  // explicit override must still reach white and reset the exact source pixels.
  assert.ok(result.white.mean>result.before.mean+10,JSON.stringify(result));
  assert.ok(result.white.mean>=254,JSON.stringify(result));
  assert.deepEqual(result.edited,[[1,1,1],[.5,.5,.5]]);
  assert.deepEqual(result.restored,result.original);assert.deepEqual(result.opacityOnly,result.original);
  assert.ok(Math.abs(result.reset.mean-result.before.mean)<.1,JSON.stringify(result));
  assert.equal(result.sameMap,true);assert.equal(result.isolated,true);assert.deepEqual(shaderErrors,[]);
  console.log('PASS: real PMX eye-white recolour brightens in WebGL, preserves shared iris atlas, restores original pixels and separates opacity',JSON.stringify(result));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
