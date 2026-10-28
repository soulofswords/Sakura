const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});try{
 const page=await browser.newPage();let releaseRead,releaseSave;const writes=[];
 await page.route('http://appearance.test/**',async route=>{
  if(new URL(route.request().url()).pathname==='/api/settings'){
   if(route.request().method()==='GET'){await new Promise(resolve=>releaseRead=resolve);return route.fulfill({json:{ui_theme:'light'}});}
   writes.push(route.request().postDataJSON().ui_theme);if(writes.length===1)await new Promise(resolve=>releaseSave=resolve);
   return route.fulfill({json:{ok:true}});
  }
  return route.fulfill({contentType:'text/html',body:'<div id="tab-theme"></div>'});
 });
 await page.goto('http://appearance.test/');
 await page.addScriptTag({content:fs.readFileSync('static/js/appearance.js','utf8').replace('export function','function')});
 await page.locator('[data-appearance-select]').selectOption('dark');
 while(!releaseSave||!releaseRead)await new Promise(resolve=>setTimeout(resolve,10));
 await page.locator('[data-appearance-select]').selectOption('system');releaseRead();
 await page.waitForTimeout(80);
 assert.equal(await page.locator('[data-appearance-select]').inputValue(),'system','A slow startup response cannot overwrite the user choice');
 assert.deepEqual(writes,['dark'],'Only one settings write may be in flight');
 releaseSave();await page.waitForFunction(()=>localStorage.getItem('sakura_ui_theme')==='system');
 const deadline=Date.now()+3000;while(writes.length<2&&Date.now()<deadline)await new Promise(resolve=>setTimeout(resolve,10));
 assert.deepEqual(writes,['dark','system'],'Settings writes retain selection order');
 console.log('PASS: stale settings read ignored and appearance saves serialized.');
}finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
