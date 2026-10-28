const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});try{
 const page=await browser.newPage({viewport:{width:390,height:844}});await page.emulateMedia({colorScheme:'light'});
 await page.route('http://mobile.test/**',route=>{const path=new URL(route.request().url()).pathname;if(path==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync('android/assets/index.html','utf8').replace(/<script type="module"[^>]*>[\s\S]*?<\/script>/g,'')});if(path==='/local-viewer.html')return route.fulfill({contentType:'text/html',body:fs.readFileSync('android/assets/local-viewer.html','utf8').replace(/<script type="module"[^>]*>[\s\S]*?<\/script>/g,'')});return route.fulfill({path:'android/assets'+path});});
 await page.goto('http://mobile.test/');assert.deepEqual(await page.locator('#mobile-appearance-home option').allTextContents(),['Light','Dark','System']);
 assert.equal(await page.locator('html').getAttribute('data-ui-theme'),'light');
 await page.locator('#mobile-appearance-home select').selectOption('dark');assert.equal(await page.locator('html').getAttribute('data-ui-theme'),'dark');
 assert.equal(await page.locator('#local-stage-panel select[data-mobile-appearance]').inputValue(),'dark');
 await page.route('https://models.sakura.invalid/**',route=>{
  const path=new URL(route.request().url()).pathname;
  if(path==='/local-viewer.html')return route.fulfill({contentType:'text/html',body:fs.readFileSync('android/assets/local-viewer.html','utf8').replace(/<script type="module"[^>]*>[\s\S]*?<\/script>/g,'')+'<script>parent.postMessage({type:"avatar-ready"},"http://mobile.test");</script>'});
  if(path==='/mobile-appearance.js')return route.fulfill({contentType:'text/javascript',body:fs.readFileSync('android/assets/mobile-appearance.js','utf8').replaceAll('https://appassets.androidplatform.net','http://mobile.test')});
  return route.fulfill({path:'android/assets'+path});
 });
 const navigation=page.waitForEvent('framenavigated',{predicate:frame=>frame.url().startsWith('https://models.sakura.invalid')});
 await page.evaluate(()=>{document.getElementById('local-avatar').src='https://models.sakura.invalid/local-viewer.html';});
 await page.frameLocator('#local-avatar').locator('html').waitFor({state:'attached'});
 const renderer=await navigation;
 await renderer.waitForFunction(()=>document.documentElement.dataset.uiTheme==='dark');
 await page.locator('#mobile-appearance-home select').selectOption('light');await renderer.waitForFunction(()=>document.documentElement.dataset.uiTheme==='light');
 await page.reload();assert.equal(await page.locator('#mobile-appearance-home select').inputValue(),'light');
 await page.locator('#mobile-appearance-home select').selectOption('system');await page.emulateMedia({colorScheme:'dark'});await page.waitForFunction(()=>document.documentElement.dataset.uiTheme==='dark');
 for(const width of [320,390,768]){await page.setViewportSize({width,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Appearance stays within the phone viewport');}
 console.log('PASS: three mobile themes, saved selection, live system changes, synchronized avatar iframe and both selectors, 320/390/768 widths.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
