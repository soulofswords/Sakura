const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});try{
 const page=await browser.newPage();let html=fs.readFileSync('static/index.html','utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
 await page.route('http://pair.test/**',route=>{if(route.request().url().includes('/api/'))return route.fulfill({contentType:'application/json',body:JSON.stringify({enabled:true,name:'My PC',code:'123456',addresses:['http://192.168.1.103:8771'],devices:[]})});return route.fulfill({contentType:'text/html',body:html});});
 await page.goto('http://pair.test/');await page.evaluate(()=>{document.getElementById('settings-modal').classList.remove('hidden');document.getElementById('tab-general').classList.add('active');});
 const source=fs.readFileSync('static/js/mobile-link.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export function','function');
 await page.addScriptTag({content:'class HeadPoseFilter{};'+source+';installMobileLink(()=>null,()=>null,()=>{},()=>{});'});
 await page.waitForFunction(()=>document.getElementById('phone-link-code').value==='123456');
 assert.ok(!(await page.locator('#phone-link-status').textContent()).includes('http://'));
 assert.match(await page.locator('#phone-link-status').textContent(),/My PC/);
 assert.equal(await page.locator('#phone-link-address').isVisible(),false);
 assert.equal(await page.locator('#phone-link-copy-address').isVisible(),false);
 assert.equal(await page.locator('#phone-link-code').isVisible(),true);
 await page.locator('#phone-link-advanced summary').click();assert.equal(await page.locator('#phone-link-address').isVisible(),true);
 console.log('PASS: code-first PC instructions, no visible HTTP field, Advanced retains troubleshooting fallback.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
