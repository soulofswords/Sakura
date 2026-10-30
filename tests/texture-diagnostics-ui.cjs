const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const source=fs.readFileSync('static/js/texture-diagnostics.js','utf8');
  let repairable=true;
  await page.route('http://sakura.test/**',route=>{
   if(route.request().url().endsWith('texture-diagnostics.js'))return route.fulfill({contentType:'text/javascript',body:source});
   if(route.request().url().endsWith('texture-diagnose'))return route.fulfill({json:{slots:[{material:0,slot:'diffuse',reference:'hair.png',resolved:'textures/hair.png',status:repairable?'repairable':'ok'}]}});
   if(route.request().url().endsWith('texture-material'))return route.fulfill({json:{saved:true}});
   return route.fulfill({contentType:'text/html',body:'<button id="model-texture-snapshot-check">Take snapshot and check textures</button><p id="model-texture-check-status"></p><img id="model-texture-before-image" hidden><img id="model-texture-after-image" hidden>'});
  });
  await page.goto('http://sakura.test/');
  await page.evaluate(async()=>{
   const {installTextureDiagnostics}=await import('/texture-diagnostics.js');
   window.captures=0;window.reloads=0;window.key='pmx/one.pmx';window.editorCalls=[];
   window.pywebview={api:{open_pmx_editor:async key=>{editorCalls.push(key);return {opened:true,model:key};}}};
   const vector=value=>({value,clone(){return vector(this.value);},copy(other){this.value=other.value;return this;}});
   const root=()=>({traverse(){},position:vector(3),quaternion:vector(180),scale:vector(1),updateMatrixWorld(){}});
   const camera=value=>({value,clone(){return camera(this.value);},copy(other){this.value=other.value;},updateProjectionMatrix(){},updateMatrixWorld(){}});
   const viewer=window.viewer={model:root(),camera:camera(180),controls:{target:vector(7)},pmxTextureSlots:[{material:0,slot:'diffuse',original:'hair.png'}],captureSpoutFrame(){window.captures++;return {width:2,height:2,pixels:new Uint8Array(16).fill(255)};}};
   window.diagnostics=installTextureDiagnostics(()=>viewer,()=>window.key,async()=>{window.reloads++;viewer.model=root();viewer.model.position.value=0;viewer.model.quaternion.value=0;viewer.camera.value=0;viewer.controls.target.value=0;});
   diagnostics.refresh();
  });
  await page.click('#model-texture-snapshot-check');
  await page.waitForFunction(()=>document.getElementById('model-texture-check-status').textContent.includes('Snapshots and report saved locally'));
  const result=await page.evaluate(async()=>{
   const saved=await new Promise((resolve,reject)=>{const r=indexedDB.open('sakura-texture-diagnostics',1);r.onsuccess=()=>{const db=r.result,get=db.transaction('models').objectStore('models').get('pmx/one.pmx');get.onsuccess=()=>{resolve(get.result);db.close();};get.onerror=reject;};});
   return {captures,reloads,editorCalls,view:[viewer.camera.value,viewer.controls.target.value,viewer.model.position.value,viewer.model.quaternion.value],report:saved.report,before:saved.before.size,after:saved.after.size,visible:!document.getElementById('model-texture-after-image').hidden};
  });
  assert.equal(result.captures,2);assert.equal(result.reloads,1);assert.equal(result.report.repaired,1);assert.ok(result.before>0&&result.after>0&&result.visible);
  assert.deepEqual(result.editorCalls,['pmx/one.pmx']);assert.equal(result.report.editorOpened,true);
  assert.deepEqual(result.view,[180,7,3,180],'Reload retains back view, model position, rotation and camera target');
  repairable=false;
  await page.click('#model-texture-snapshot-check');
  await page.waitForFunction(()=>!document.getElementById('model-texture-snapshot-check').disabled);
  const refreshed=await page.evaluate(()=>({reloads,revision:viewer.textureReloadRevision,status:document.getElementById('model-texture-check-status').textContent}));
  assert.equal(refreshed.reloads,2,'Valid files still need fresh GPU textures after an earlier fallback');assert.ok(refreshed.revision>1000);assert.match(refreshed.status,/0 path repairs saved/);
  await page.evaluate(async()=>{
   const {installTextureDiagnostics}=await import('/texture-diagnostics.js');
   window.appearanceCalls=0;window.pywebview.api.capture_pmx_appearance_reference=async()=>({});
   diagnostics=installTextureDiagnostics(()=>viewer,()=>window.key,async()=>{},async()=>{appearanceCalls++;return {matched:true,improved:true};});
  });
  await page.click('#model-texture-snapshot-check');await page.waitForFunction(()=>!document.getElementById('model-texture-snapshot-check').disabled);
  assert.equal(await page.evaluate(()=>appearanceCalls),1,'Texture check invokes the shared real-reference appearance callback after repairs');
  assert.match(await page.locator('#model-texture-check-status').textContent(),/actual PMX Editor reference/);
  await page.evaluate(()=>{window.key='vrm/next.vrm';diagnostics.refresh();});
  assert.equal(await page.locator('#model-texture-before-image').getAttribute('src'),null,'Changing models clears prior snapshot');
  await page.evaluate(()=>{viewer.captureSpoutFrame=()=>null;});
  await page.click('#model-texture-snapshot-check');await page.waitForFunction(()=>document.getElementById('model-texture-check-status').textContent.includes('finish loading'));
  assert.equal(await page.locator('#model-texture-snapshot-check').isEnabled(),true,'Capture failure restores button');assert.deepEqual(errors,[]);
  console.log('PASS: texture snapshot button captures offscreen before/after, reloads repaired model, saves local report and recovers on model/capture changes');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
