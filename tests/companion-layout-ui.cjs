const fs=require('fs'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const page=await browser.newPage();
 let html=fs.readFileSync('static/index.html','utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
 html=html.replace(/<link[^>]*rel="stylesheet"[^>]*>/,'<style>'+fs.readFileSync('static/css/style.css','utf8')+'</style>');
 for(const width of [320,460,1100]){
  await page.goto("about:blank");await page.setViewportSize({width,height:760});await page.setContent(html);
  await page.addScriptTag({content:fs.readFileSync("static/js/companion-toolbar.js","utf8").replace("export function","function")});
  await page.evaluate(()=>{window.sakuraCompanionToolbar=installCompanionToolbar();});
  const app=fs.readFileSync("static/js/app.js","utf8");
  const dropdown=app.slice(app.indexOf("function initCustomDropdown("),app.indexOf("let pmxFolderPath"));
  await page.addScriptTag({content:"const themePopover=null;"+dropdown+"\ninitCustomDropdown('model-dropdown',document.getElementById('model-select'));"});
  await page.evaluate(()=>{document.body.className='desktop-companion native-renderer';document.getElementById('win-controls').style.display='flex';});
  const compact=await page.locator('#top-bar').boundingBox();
  assert.ok(compact.height<=54,`compact header height ${compact.height}`);
  assert.equal(await page.locator('#companion-toolbar').isVisible(),false);
  assert.equal(await page.locator('#companion-toolbar-toggle').isVisible(),true);
  const close=await page.locator('#win-close-btn').boundingBox();assert.ok(close.x+close.width<=width);
  await page.locator('#companion-toolbar-toggle').click();
  assert.equal(await page.locator('#companion-toolbar').isVisible(),true);
  const expanded=await page.locator('#top-bar').boundingBox();assert.equal(expanded.height,compact.height,'Menu must not change the titlebar layout');
  await page.locator('#model-dropdown-trigger').click();
  const menu=page.locator('#model-dropdown-menu');assert.equal(await menu.isVisible(),true);
  const box=await menu.boundingBox();assert.ok(box.x>=0 && box.x+box.width<=width && box.y+box.height<=760);
  await page.locator('#companion-toolbar-toggle').click();assert.equal(await page.locator('#companion-toolbar').isVisible(),false);
  await page.locator('#companion-toolbar-toggle').click();await page.keyboard.press('Escape');assert.equal(await page.locator('#companion-toolbar').isVisible(),false);

  await page.evaluate(()=>{document.body.className='native-library native-renderer';});
  assert.equal(await page.locator('#companion-toolbar').isVisible(),true);
  assert.equal(await page.locator('#companion-toolbar-toggle').isVisible(),false);
 }
 await page.evaluate(()=>{
  const viewer=document.getElementById('viewer');
  const live=document.createElement('canvas'),held=document.createElement('canvas');
  live.id='test-live-canvas';held.id='test-held-canvas';held.className='model-held-frame';
  viewer.append(live,held);viewer.classList.add('model-frame-held');
 });
 assert.equal(await page.locator('#test-live-canvas').evaluate(element=>getComputedStyle(element).visibility),'hidden');
 assert.equal(await page.locator('#test-held-canvas').evaluate(element=>getComputedStyle(element).visibility),'visible');
 await page.evaluate(()=>{document.getElementById('test-held-canvas').remove();document.getElementById('viewer').classList.remove('model-frame-held');});
 assert.equal(await page.locator('#test-live-canvas').evaluate(element=>getComputedStyle(element).visibility),'visible');
 await browser.close();console.log('PASS: transparent saved frame replaces the live canvas and restores it without overlap');console.log('PASS: 320/460/1100px companion header, contained expanded controls and full library restoration');
})().catch(e=>{console.error(e);process.exitCode=1;});
