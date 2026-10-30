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

  await page.evaluate(async()=>{
   await auditModel('pmx/Richie/Richie.pmx');
   const host=document.createElement('div');host.id='model-lighting-controls';host.style.cssText='position:relative;z-index:9;background:white';document.body.append(host);
   window.appearanceModule=await import('/static/js/pmx-render-controls.js?v=1');
   window.appearanceKey='pmx/Richie/Richie.pmx';
   window.editorCalls=[];window.pywebview={api:{model_load_status(){},model_frame_status(){},capture_pmx_appearance_reference:async key=>{
       editorCalls.push(key);const saved=appearanceModule.readPmxAppearance(key);
       appearanceModule.applyPmxAppearance(auditViewer.model,{brightness:1});
       const frame=auditViewer.captureTextureDiagnosticFrame(192),canvas=document.createElement('canvas');canvas.width=frame.width;canvas.height=frame.height;
       canvas.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(frame.pixels),frame.width,frame.height),0,0);
       const image=canvas.toDataURL();appearanceModule.applyPmxAppearance(auditViewer.model,saved);
       const materials=auditViewer.model.material,visibility=materials.map(m=>m.visible);
       appearanceModule.applyPmxAppearance(auditViewer.model,{brightness:1});materials.forEach((m,i)=>m.visible=i===0);
       const partFrame=auditViewer.captureTextureDiagnosticFrame(192);canvas.width=partFrame.width;canvas.height=partFrame.height;canvas.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(partFrame.pixels),partFrame.width,partFrame.height),0,0);
       const partImage=canvas.toDataURL();materials.forEach((m,i)=>m.visible=visibility[i]);appearanceModule.applyPmxAppearance(auditViewer.model,saved);
       return {model:key,image,parts:[{material:0,image:partImage}],lighting:{ambient:[255,255,255]}};
     }}};
   window.appearanceUI=appearanceModule.installPmxAppearance(()=>auditViewer,()=>appearanceKey);await appearanceUI.refresh();
  });
  assert.equal(await page.locator('#pmx-appearance-controls input[type=range]').count(),8);
  await page.locator('#pmx-appearance-brightness').evaluate(input=>{input.value='50';input.dispatchEvent(new Event('input'));});
  const result=await page.evaluate(async()=>{
   const {readPmxAppearance,pmxAppearanceKey,normalizePmxAppearance}=appearanceModule;
   const saved=readPmxAppearance('/models/pmx/Richie/Richie.pmx?refresh=2');
   const sample=()=>{auditViewer._renderFrame();const gl=auditViewer.renderer.getContext(),p=new Uint8Array(gl.drawingBufferWidth*gl.drawingBufferHeight*4);gl.readPixels(0,0,gl.drawingBufferWidth,gl.drawingBufferHeight,gl.RGBA,gl.UNSIGNED_BYTE,p);let n=0,sum=0;for(let i=0;i<p.length;i+=4)if(p[i+3]>240){sum+=p[i]+p[i+1]+p[i+2];n++;}return sum/Math.max(1,3*n);};
   const dim=sample();
   await auditModel('pmx/Richie/Richie.pmx');const reload=sample();
   const uniforms=auditViewer.model.material[0].uniforms;
   const persisted=uniforms.sakuraPmxControl_brightness.value;
   appearanceModule.applyPmxAppearance(auditViewer.model,{brightness:1});const bright=sample();
   appearanceModule.applyPmxAppearance(auditViewer.model,saved);
   return {saved,dim,reload,bright,persisted,other:readPmxAppearance('pmx/other.pmx'),bounded:normalizePmxAppearance({ambient:Infinity,brightness:999,saturation:-4}),key:pmxAppearanceKey('/models/pmx/Miku%20universe/a.pmx?x=1')};
  });
  assert.equal(result.saved.brightness,.5);assert.equal(result.persisted,.5);assert.equal(result.other.brightness,1);
  assert.ok(result.dim<result.bright*.7,JSON.stringify(result));assert.ok(Math.abs(result.reload-result.dim)<3,JSON.stringify(result));
  assert.equal(result.bounded.ambient,1);assert.equal(result.bounded.brightness,2);assert.equal(result.bounded.saturation,0);assert.equal(result.key,'pmx/Miku universe/a.pmx');
  await page.locator('#pmx-appearance-snapshot').click();
  await page.waitForFunction(()=>document.querySelector('#pmx-appearance-controls [role=status]').textContent.includes('Texture files are unchanged'));
  assert.equal(await page.evaluate(()=>editorCalls.length),1);
  assert.ok(Number(await page.locator('#pmx-appearance-brightness').inputValue())>50);
  await page.locator('#pmx-appearance-undo').click();
  await page.waitForFunction(()=>document.querySelector('#pmx-appearance-brightness').value==='50');
  assert.equal(await page.locator('#pmx-appearance-brightness').inputValue(),'50');
  assert.equal(await page.locator("#pmx-appearance-controls img[alt=\"Saved full-model appearance snapshot\"]").evaluate(image=>image.naturalWidth>0),true);
  await page.evaluate(async()=>{await appearanceUI.refresh();});
  assert.equal(await page.locator("#pmx-appearance-controls img[alt=\"Saved full-model appearance snapshot\"]").evaluate(image=>!!image.src&&!image.hidden),true);
  await page.locator('#pmx-appearance-reset').click();
  assert.equal(await page.locator('#pmx-appearance-brightness').inputValue(),'100');
  await page.evaluate(async()=>{appearanceKey='pmx/other.pmx';await appearanceUI.refresh();});
  assert.equal(await page.locator("#pmx-appearance-controls img[alt=\"Saved full-model appearance snapshot\"]").evaluate(image=>image.hidden),true);
  // An all-translucent model exports no opaque material samples. The UI must
  // still permit a measured whole-frame comparison instead of rejecting it.
  await page.evaluate(async()=>{
   appearanceKey='pmx/Richie/Richie.pmx';await appearanceUI.refresh();
   const capture=window.pywebview.api.capture_pmx_appearance_reference;
   window.pywebview.api.capture_pmx_appearance_reference=async key=>({...await capture(key),parts:[]});
   window.wholeMatch=await appearanceUI.match();
  });
  assert.equal(await page.evaluate(()=>wholeMatch.matched),true);
  assert.match(await page.locator('#pmx-appearance-controls [role=status]').textContent(),/Texture files are unchanged/);
  await page.evaluate(async()=>{appearanceKey='pmx/Richie/Richie.pmx';await appearanceUI.refresh();window.pywebview.api.capture_pmx_appearance_reference=async()=>{throw Error('Reference timed out');};});
  await page.locator('#pmx-appearance-snapshot').click();
  await page.waitForFunction(()=>!document.querySelector('#pmx-appearance-snapshot').disabled);
  assert.match(await page.locator('#pmx-appearance-controls [role=status]').textContent(),/Reference timed out/);
  assert.equal(await page.locator('#pmx-appearance-brightness').inputValue(),'100');
  assert.equal(await page.locator('#pmx-appearance-reset').isEnabled(),true);
  await page.evaluate(async()=>{appearanceKey='avatar.vrm';await appearanceUI.refresh();});
  assert.equal(await page.locator('#pmx-appearance-controls').evaluate(element=>element.hidden),true);
  assert.deepEqual(shaderErrors,[]);
  console.log('PASS: eight sliders, real WebGL brightness, per-model persistence on reload, bounds, separate saved appearance snapshot, editor launch and reset',JSON.stringify(result));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
