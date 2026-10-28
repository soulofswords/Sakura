const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});try{
 const page=await browser.newPage();await page.setContent('<main></main>');await page.addScriptTag({content:fs.readFileSync('static/js/agent-memory.js','utf8')});
 await page.evaluate(()=>{window.calls=[];window.memory=installAgentMemory({api:async(...args)=>{calls.push(args);return {};},perform:async fn=>fn(),refresh:async()=>{}});document.getElementById('agent-memory').hidden=false;memory.render({enabled:true,notes:'Notes',profile:'Short answers',procedures:[{id:'one',category:'document',tools:['files.list','files.read'],successes:2}]});});
 await page.fill('#learning-profile','Concise replies');await page.click('#learning-save');assert.ok(await page.evaluate(()=>calls.some(c=>c[0]==='memory'&&c[1].profile==='Concise replies')));
 await page.getByRole('textbox',{name:'Name for document skill'}).fill('document-review');await page.getByRole('button',{name:'Save as skill',exact:true}).click();assert.ok(await page.evaluate(()=>calls.some(c=>c[0]==='memory/one/skill'&&c[1].name==='document-review')));
 await page.getByRole('button',{name:'Forget procedure',exact:true}).click();assert.ok(await page.evaluate(()=>calls.some(c=>c[0]==='memory/one'&&c[2]==='DELETE')));
 console.log('PASS: persistent memory settings, reviewed learned-skill creation and individual deletion reach the API.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
