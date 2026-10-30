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
   const loaded=await auditModel('pmx/Miku universe/Miku/Z Ice Miku 2.0/Model/TDA Ice Miku 2.Pmx');
   const v=auditViewer,materials=v.model.material;
   const target=materials[35];
   materials.forEach(m=>m.visible=m===target);
   function measure(){const frame=v.captureTextureDiagnosticFrame(960);let n=0,s=[0,0,0];for(let i=0;i<frame.pixels.length;i+=4)if(frame.pixels[i+3]>240){n++;for(let j=0;j<3;j++)s[j]+=frame.pixels[i+j];}return {n,rgb:s.map(x=>x/Math.max(n,1))};}
   const corrected=measure();
   target.uniforms.sakuraPmxLitAmbient.value=0;const old=measure();target.uniforms.sakuraPmxLitAmbient.value=1;
   materials.forEach(m=>m.visible=true);
   const frame=v.captureTextureDiagnosticFrame(960),canvas=document.createElement('canvas');canvas.width=frame.width;canvas.height=frame.height;
   canvas.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(frame.pixels),frame.width,frame.height),0,0);
   return {ok:loaded.ok,corrected,old,preview:canvas.toDataURL()};
  });
  assert.equal(result.ok,true);assert.ok(result.corrected.n>100);
  const cast=row=>row.rgb[2]-(row.rgb[0]+row.rgb[1])/2;
  assert.ok(cast(result.corrected)<cast(result.old)*.6,JSON.stringify(result.corrected));
  assert.ok(result.corrected.rgb[0]>result.old.rgb[0]+30);
  fs.writeFileSync('F:/AI/assistant/private-security-hardening/texture-check-2026-10-29/ice-corrected-full.png',Buffer.from(result.preview.split(',')[1],'base64'));
  delete result.preview;assert.deepEqual(shaderErrors,[]);
  console.log('PASS: Ice Miku shared flat-key correction reduces blue/purple bias without rewriting material colours',JSON.stringify(result));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
