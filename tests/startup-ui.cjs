const fs=require('fs'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1100,height:760}});
  let html=fs.readFileSync('static/index.html','utf8').replace(/<script\b[^>]*type="module"[^>]*>[\s\S]*?<\/script>/gi,'');
  await page.route('http://sakura.test/**',route=>{
   const pathname=new URL(route.request().url()).pathname;
   if(pathname.startsWith('/static/'))return route.fulfill({path:'.'+pathname});
   return route.fulfill({contentType:'text/html',body:html});
  });
  await page.goto('http://sakura.test/?library=1&upload=1&tracking=1');
  assert.equal(await page.locator('#startup-render-status').isVisible(),true);
  assert.equal(await page.locator('#top-bar').isVisible(),false,'Old toolbar never appears before module initialization');
  assert.equal(await page.locator('#viewer').isVisible(),false);
  // The old app handler may still toggle its legacy splash during startup.
  await page.evaluate(()=>document.getElementById('model-upload-splash').classList.remove('hidden'));
  assert.equal(await page.locator('#model-upload-splash').isVisible(),false,'No second logo screen in VTuber startup');
  await page.addScriptTag({content:fs.readFileSync('static/js/vtuber-studio.js','utf8').replace('export function','function')});
  await page.evaluate(()=>document.body.classList.add('tracking-only'));
  await page.waitForFunction(()=>document.body.classList.contains('studio-ui-active'));
  assert.equal(await page.locator('#studio-dock').isVisible(),false,'New UI also remains covered until renderer ready');
  await page.addScriptTag({content:fs.readFileSync('static/js/startup-presentation.js','utf8').replace('export async function','async function')+';window.finishTest=finishStartupPresentation;'});
  await page.evaluate(()=>window.finishTest(null));
  assert.equal(await page.locator('#startup-render-status').isVisible(),false);
  assert.equal(await page.locator('#studio-dock').isVisible(),true);
  assert.equal(await page.locator('#companion-toolbar').isVisible(),false);
  assert.equal(await page.locator('#model-upload-splash').isVisible(),false);
  assert.equal(await page.locator('#studio-lock-label').count(),0);
  await page.locator('#studio-model-lock').click();assert.equal(await page.locator('#studio-model-lock').getAttribute('aria-pressed'),'true');
  console.log('PASS: cold startup covers old UI, animated first screen, no second splash, ready reveals VTuber layout, lock works without redundant label.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
