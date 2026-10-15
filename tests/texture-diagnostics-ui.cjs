const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const source=fs.readFileSync('static/js/texture-diagnostics.js','utf8');
  await page.route('http://sakura.test/**',route=>{
   if(route.request().url().endsWith('texture-diagnostics.js'))return route.fulfill({contentType:'text/javascript',body:source});
   if(route.request().url().endsWith('texture-diagnose'))return route.fulfill({json:{slots:[{material:0,slot:'diffuse',reference:'hair.png',resolved:'textures/hair.png',status:'repairable'}]}});
   if(route.request().url().endsWith('texture-material'))return route.fulfill({json:{saved:true}});
   return route.fulfill({contentType:'text/html',body:'<button id="model-texture-snapshot-check">Take snapshot and check textures</button><p id="model-texture-check-status"></p><img id="model-texture-before-image" hidden><img id="model-texture-after-image" hidden>'});
  });
  await page.goto('http://sakura.test/');
  await page.evaluate(async()=>{
   const {installTextureDiagnostics}=await import('/texture-diagnostics.js');
   window.captures=0;window.reloads=0;window.key='pmx/one.pmx';
   const viewer=window.viewer={model:{traverse(){}},pmxTextureSlots:[{material:0,slot:'diffuse',original:'hair.png'}],captureSpoutFrame(){window.captures++;return {width:2,height:2,pixels:new Uint8Array(16).fill(255)};}};
   window.diagnostics=installTextureDiagnostics(()=>viewer,()=>window.key,async()=>{window.reloads++;viewer.model={traverse(){}};});
   diagnostics.refresh();
  });
  await page.click('#model-texture-snapshot-check');
  await page.waitForFunction(()=>document.getElementById('model-texture-check-status').textContent.includes('Snapshots and report saved locally'));
  const result=await page.evaluate(async()=>{
   const saved=await new Promise((resolve,reject)=>{const r=indexedDB.open('sakura-texture-diagnostics',1);r.onsuccess=()=>{const db=r.result,get=db.transaction('models').objectStore('models').get('pmx/one.pmx');get.onsuccess=()=>{resolve(get.result);db.close();};get.onerror=reject;};});
   return {captures,reloads,report:saved.report,before:saved.before.size,after:saved.after.size,visible:!document.getElementById('model-texture-after-image').hidden};
  });
  assert.equal(result.captures,2);assert.equal(result.reloads,1);assert.equal(result.report.repaired,1);assert.ok(result.before>0&&result.after>0&&result.visible);
  await page.evaluate(()=>{window.key='vrm/next.vrm';diagnostics.refresh();});
  assert.equal(await page.locator('#model-texture-before-image').getAttribute('src'),null,'Changing models clears prior snapshot');
  await page.evaluate(()=>{viewer.captureSpoutFrame=()=>null;});
  await page.click('#model-texture-snapshot-check');await page.waitForFunction(()=>document.getElementById('model-texture-check-status').textContent.includes('finish loading'));
  assert.equal(await page.locator('#model-texture-snapshot-check').isEnabled(),true,'Capture failure restores button');assert.deepEqual(errors,[]);
  console.log('PASS: texture snapshot button captures offscreen before/after, reloads repaired model, saves local report and recovers on model/capture changes');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
