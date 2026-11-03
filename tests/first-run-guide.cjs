const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{
 const code=fs.readFileSync(process.argv[2]||'static/js/first-run-guide.js','utf8');
 for(const mode of ['companion','vtuber','agent','mobile']){
  const page=await browser.newPage({viewport:{width:320,height:640}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://setup.test/**',route=>route.fulfill({contentType:'text/html',body:'<html><head><title>'+ (mode==='agent'?'Sakura Agent':'Sakura')+'</title></head><body style="background:#20242b">'+(mode==='mobile'?'<div id="app-modes"></div><div id="mobile-appearance-home"></div><button id="mode-local">Use phone</button><details id="phone-settings"></details>':'<div id="tab-general"></div><div id="agent-metrics"></div>')+'</body></html>'}));
  await page.goto('http://setup.test/');await page.evaluate(mode=>window.SAKURA_EDITION=mode,mode);await page.addScriptTag({content:code});
  const dialog=page.locator('#sakura-setup-guide');await dialog.waitFor({state:'visible'});
  // Shared app button styling must not reveal a hidden, unlabelled action.
  await page.addStyleTag({content:'button{display:inline-flex}'});
  assert.equal(await dialog.locator('.setup-show').isVisible(),false,'Welcome has no blank action for '+mode);
  assert.equal(await dialog.locator('.setup-back').isDisabled(),true);
  assert.equal(await dialog.evaluate(el=>el.getBoundingClientRect().width<=innerWidth),true);
  assert.notEqual(await dialog.evaluate(el=>getComputedStyle(el).backgroundColor),'rgba(0, 0, 0, 0)');
  await dialog.locator('.setup-next').click();
  if(mode!=='mobile'){assert.equal(await dialog.locator('.setup-show').isVisible(),true);assert.ok((await dialog.locator('.setup-show').textContent()).trim());}
  await dialog.locator('.setup-back').click();assert.ok((await dialog.locator('.setup-progress').textContent()).includes('1 of'));
  assert.equal(await dialog.locator('.setup-show').isVisible(),false,'Going back hides the action again');
  await page.reload();await page.evaluate(mode=>window.SAKURA_EDITION=mode,mode);await page.addScriptTag({content:code});await page.waitForTimeout(400);
  assert.equal(await dialog.isVisible(),false,'An interrupted first tour does not auto-open on the second launch');
  await page.locator('#sakura-reopen-setup').click();
  for(let i=0;i<10&&await dialog.isVisible();i++)await dialog.locator('.setup-next').click();
  assert.equal(await dialog.isVisible(),false);await page.reload();await page.evaluate(mode=>window.SAKURA_EDITION=mode,mode);await page.addScriptTag({content:code});await page.waitForTimeout(400);
  assert.equal(await page.locator('#sakura-setup-guide').isVisible(),false,'Completion survives relaunch for '+mode);
  await page.locator('#sakura-reopen-setup').click();await page.locator('.setup-next').click();await page.locator('.setup-next').click();
  if(await page.locator('.setup-show').isVisible()){
   await page.locator('.setup-show').click();
   assert.equal(await dialog.isVisible(),true,'Show keeps the guide open for '+mode);
   assert.equal(await dialog.evaluate(el=>el.matches(':modal')),false,'Underlying app remains interactive');
  }
  await page.locator('.setup-step').first().click();
  assert.equal(await dialog.locator('.setup-show').isVisible(),false);
  assert.equal(await page.locator('[aria-current="step"]').textContent(),'1');
  await page.locator('.setup-skip').click();assert.deepEqual(errors,[]);await page.close();
 }
 console.log('PASS: Mobile, Companion, VTuber and Agent first run, persistence, nonmodal Show, step navigation and reopening at 320px');
 }finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
