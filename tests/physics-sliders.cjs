const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.AUDIT_CHROMIUM,args:['--use-angle=d3d11']});
 try{
  const page=await browser.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/api/settings',async route=>{
   if(route.request().method()!=='POST')return route.continue();
   await route.fulfill({json:{ok:true,settings:route.request().postDataJSON()}});
  });
  await page.goto('http://127.0.0.1:8766/?library=1');
  await page.waitForFunction(()=>document.querySelector('#model-select')?.options.length>10);
  await page.locator('#settings-btn').click();
  await page.locator('[data-tab="models"]').click();
  assert.equal(await page.locator('[data-physics]').count(),0);
  assert.ok(await page.locator('#physics-wind').isVisible());
  const change=async(id,value)=>page.locator(id).evaluate((element,value)=>{
   element.value=value; element.dispatchEvent(new Event('input',{bubbles:true}));
  },String(value));
  await change('#physics-strength',75); await change('#physics-wind',42);
  assert.equal(await page.locator('#physics-strength-value').textContent(),'75%');
  assert.equal(await page.locator('#physics-wind-value').textContent(),'42%');
  assert.deepEqual(await page.evaluate(()=>[localStorage.getItem('sakura_physics_boost'),localStorage.getItem('sakura_physics_wind')]),['0.75','0.42']);
  await page.reload();
  await page.waitForFunction(()=>document.querySelector('#physics-strength').value==='75' && document.querySelector('#physics-wind').value==='42');
  await change('#physics-strength',0);
  assert.equal(await page.locator('#physics-strength-value').textContent(),'Natural (0%)');
  await page.locator('#settings-btn').click();
  await page.locator('[data-tab="models"]').click();
  await page.locator('#physics-enabled').uncheck();
  assert.equal(await page.locator('#physics-strength-value').textContent(),'Off');
  assert.ok(await page.locator('#physics-strength').isDisabled());
  await page.locator('#physics-enabled').check();
  assert.equal(await page.locator('#physics-strength-value').textContent(),'Natural (0%)');
  await change('#physics-strength',100); await change('#physics-wind',0);
  assert.equal(await page.locator('#physics-wind-value').textContent(),'0%');
  assert.deepEqual(errors,[]);
  console.log('PASS: visible sliders, saved boost/wind, reload, zero boost retains natural physics and separate Off/resume');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
