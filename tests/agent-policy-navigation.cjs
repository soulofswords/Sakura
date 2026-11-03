const fs=require('node:fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{
 const page=await browser.newPage();const html=fs.readFileSync('static/assets/agent.html','utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace(/<link[^>]*rel="stylesheet"[^>]*>/g,'');
 await page.route('http://policy.test/',r=>r.fulfill({contentType:'text/html',body:html}));await page.goto('http://policy.test/');
 await page.addScriptTag({content:fs.readFileSync('static/js/agent-studio.js','utf8')});
 await page.evaluate(()=>{window.pendingRead=null;window.pendingWrite=null;window.posts=[];installAgentStudio({api:(path,body)=>{if(!body)return new Promise(resolve=>pendingRead=resolve);posts.push(body.mode);return new Promise((resolve,reject)=>pendingWrite={resolve,reject});},perform:fn=>fn().catch(error=>document.getElementById('status').textContent=error.message)});});
 await page.locator('[data-execution-mode="auto"]').click();assert.equal(await page.locator('[data-execution-mode="approval"]').isDisabled(),true);
 await page.evaluate(()=>pendingWrite.resolve({mode:'full'}));await page.waitForFunction(()=>document.getElementById('agent-execution-mode').dataset.state==='auto');
 await page.evaluate(()=>pendingRead({mode:'ask'}));assert.equal(await page.locator('#agent-execution-mode').getAttribute('data-state'),'auto');assert.equal(await page.locator('#agent-access-label').textContent(),'Full access');
 await page.locator('[data-execution-mode="approval"]').click();await page.evaluate(()=>pendingWrite.reject(new Error('Native approval denied')));await page.waitForFunction(()=>document.getElementById('status').textContent==='Native approval denied');
 assert.equal(await page.locator('#auto-plan').isChecked(),true);assert.equal(await page.locator('#agent-execution-mode').getAttribute('data-state'),'auto');assert.equal(await page.locator('[data-execution-mode="approval"]').isDisabled(),false);
 await page.locator('[data-execution-mode="approval"]').click();await page.evaluate(()=>pendingWrite.resolve({mode:'ask'}));await page.waitForFunction(()=>document.getElementById('agent-execution-mode').dataset.state==='approval');
 assert.deepEqual(await page.evaluate(()=>posts),['full','ask','ask']);
 console.log('PASS: delayed startup reads never override user approval choices; pending requests serialize and rejected changes restore the previous mode.');
}finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
