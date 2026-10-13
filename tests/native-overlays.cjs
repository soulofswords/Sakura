const fs=require('node:fs'),assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.AUDIT_CHROMIUM,args:['--use-angle=d3d11']});
 try{
  const page=await browser.newPage({viewport:{width:460,height:760}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  // UI model switches must not change the user's saved preferences.
  await page.route('**/api/settings',async route=>{
   if(route.request().method()!=='POST')return route.continue();
   await route.fulfill({json:{ok:true,settings:route.request().postDataJSON()}});
  });
  await page.goto('http://127.0.0.1:8766/?library=1');
  await page.waitForFunction(()=>document.body.classList.contains('native-renderer'));
  await page.waitForFunction(()=>document.querySelector('#model-select')?.options.length>10);
  const paths=['pmx/Ananta/Taffy/Taffy.pmx','pmx/Ananta/Ringo/Ringo.pmx','pmx/Ananta/Taffy/Taffy.pmx','pmx/Ananta/Ringo/Ringo.pmx'];
  const states=[];
  for(const path of paths){
   await page.locator('#model-select').selectOption(path,{force:true});
   await page.waitForTimeout(1600);
   await page.locator('#settings-btn').click();
   await page.locator('[data-tab="models"]').click();
   states.push(await page.evaluate(()=>{
    const elements=['#top-bar','#chat-panel','.modal-backdrop','#morph-overlay','#theme-popover'];
    return elements.map(selector=>{const e=document.querySelector(selector),style=getComputedStyle(e);return {selector,blur:style.backdropFilter,animation:style.animationName};});
   }));
   await page.locator('#settings-modal .close-btn').click();
  }
  assert.ok(states.flat().every(s=>s.blur==='none'));
  assert.ok(states.every(s=>s.find(e=>e.selector==='.modal-backdrop').animation==='none'));
  assert.deepEqual(errors,[]);
  fs.mkdirSync('audit-results/native-overlays',{recursive:true});fs.writeFileSync('audit-results/native-overlays/results.json',JSON.stringify({states,errors},null,2));
  console.log('PASS: repeated Taffy/Ringo switches and Settings open/close; native overlays have no backdrop blur or fade; no page errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
