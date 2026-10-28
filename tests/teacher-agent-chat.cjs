const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});try{
 const page=await browser.newPage();let approved=false;const posts=[];
 await page.route('http://teacher.test/**',route=>{const req=route.request();if(!req.url().includes('/api/'))return route.fulfill({contentType:'text/html',body:'<div id="messages"></div><button id="agent-mode-toggle">Agent</button>'});
  if(req.method()==='POST'){posts.push(req.postDataJSON());approved=true;}
  return route.fulfill({json:{id:'abc',planning:false,run:{goal:'Build app',workspace:'C:/Work',status:approved?'completed':'awaiting_approval',steps:[],summary:approved?'Created app.':''},pending:approved?null:{id:'action',tool:'shell.run',arguments:{command:'Write-Output hello'}}}});
 });
 await page.goto('http://teacher.test/');
 const source=fs.readFileSync('static/js/app.js','utf8');const block=source.slice(source.indexOf('function addMessage('),source.indexOf('function showTypingIndicator('));
 await page.addScriptTag({content:'const messagesEl=document.getElementById("messages");function appendEvidence(){};'+block});
 await page.evaluate(()=>addMessage('Task created','sakura',{agent_task:{id:'abc'}}));
 await page.getByRole('button',{name:'Approve step',exact:true}).waitFor();
 assert.ok((await page.locator('pre').textContent()).includes('Write-Output hello'));assert.equal(posts.length,0);
 await page.getByRole('button',{name:'Approve step',exact:true}).click();await page.waitForFunction(()=>document.querySelector('section p').textContent==='Task: completed');
 assert.deepEqual(posts,[{action:'action',approved:true}]);console.log('PASS: Companion task progress, exact action preview and explicit approval.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
