const fs=require('node:fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{
 const page=await browser.newPage({viewport:{width:390,height:844}});
 await page.route('http://growth.test/',r=>r.fulfill({contentType:'text/html',body:'<style>*{box-sizing:border-box}input,select,pre{max-width:100%}label{display:block}button{margin:5px}</style><main><section id="agent-memory-workbench"></section></main>'}));await page.goto('http://growth.test/');
 await page.addScriptTag({content:fs.readFileSync('static/js/agent-growth.js','utf8')});
 await page.evaluate(()=>{window.calls=[];window.api=async(path,body,method)=>{calls.push({path,body,method});if(path==='state')return {providers:[{id:'local',label:'Local model',ready:true}]};if(path==='model-routing')return {enabled:false,allow_cloud:false,profiles:[]};if(path==='features')return {camera_style:true};if(path==='knowledge/folders'&&!body)return {folders:[]};if(path==='speakers')return {ready:false,profiles:[]};if(path==='expenses'&&!body)return {items:[{id:'expense-one',day:'2026-11-03',amount:'12.50',currency:'INR',category:'food',note:'Lunch'}]};return {ok:true,results:[]};};installAgentGrowth({api,perform:fn=>fn().catch(e=>window.error=e.message),token:'test'});});
 await page.locator('summary').click();await page.locator('[data-folder]').fill('F:\\Documents');await page.locator('[data-semantic]').check();await page.locator('[data-index]').click();
 assert.equal(await page.evaluate(()=>calls.at(-1).body.semantic),true);
 await page.locator('[data-day]').fill('2026-11-03');await page.locator('[data-amount]').fill('123.45');await page.locator('[data-add-expense]').click();
 assert.equal(await page.evaluate(()=>calls.at(-1).body.amount),'123.45');
 await page.locator('[data-models]').click();await page.locator('[data-routing]').check();await page.locator('[data-save-routing]').click();
 assert.deepEqual(await page.evaluate(()=>calls.at(-1).body),{enabled:true,allow_cloud:false});
 await page.locator('[data-phone]').check();await page.locator('[data-features]').click();assert.equal(await page.evaluate(()=>calls.at(-1).body.phone_memory),true);assert.equal(await page.evaluate(()=>calls.at(-1).body.camera_style),true);
 await page.locator('[data-expenses]').click();await page.getByRole('button',{name:'Review deletion',exact:true}).click();assert.deepEqual(await page.evaluate(()=>calls.at(-1)),{path:'expenses/expense-one',body:undefined,method:'DELETE'});
 await page.locator('[data-speaker-status]').click();assert.match(await page.locator('[data-output]').textContent(),/"ready": false/);
 assert.equal(await page.evaluate(()=>window.error),undefined);
 console.log('PASS: folder, expense, routing, personal-feature and optional speaker controls call real API paths with reviewed fields');
}finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
