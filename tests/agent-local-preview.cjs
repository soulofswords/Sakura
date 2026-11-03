const {chromium}=require('playwright'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage();let popups=0;page.on('popup',()=>popups++);
  await page.route('http://127.0.0.1:49100/**',r=>r.fulfill({contentType:'text/html',body:'<main></main><a id="app-link" href="http://localhost:49101/">Open app</a>'}));
  await page.route('http://localhost:49101/**',r=>r.fulfill({contentType:'text/html',body:'<h1>Local app loaded</h1><input id="editable">'}));
  await page.goto('http://127.0.0.1:49100/');
  await page.addScriptTag({content:fs.readFileSync('static/js/agent-browser-panel.js','utf8')});
  await page.evaluate(()=>{
   window.calls=[];window.opened=0;window.addEventListener('sakura-agent-browser-view',()=>window.opened++);
   window.run={id:'run1',steps:[{id:'step1',tool:'local_app.open',status:'completed',result:{ok:true,presentation:'sakura-browser',url:'http://localhost:49101/'}}]};
   window.ui=window.installAgentBrowserPanel({api:async(path,args)=>window.calls.push({path,args}),perform:async fn=>fn(),selectedRun:()=>window.run,refresh:async()=>{},token:'fixture'});
   window.ui.render(window.run);
  });
  const frame=page.frameLocator('#agent-local-app');await frame.locator('h1').waitFor();
  await frame.locator('#editable').fill('Works inside Sakura');
  assert.equal(await frame.locator('#editable').inputValue(),'Works inside Sakura');
  assert.equal(await page.evaluate(()=>window.opened),1);
  await page.click('#agent-browser-close');assert.equal(await page.locator('#agent-local-app').getAttribute('src'),null);
  await page.evaluate(()=>window.ui.render(window.run));assert.equal(await page.locator('#agent-local-app').getAttribute('src'),null);
  await page.evaluate(()=>window.run.status='completed');
  await page.click('#app-link');await frame.locator('h1').waitFor();
  assert.equal(await page.evaluate(()=>window.calls.length),0,'Viewing localhost must not propose work against a completed task');
  await page.evaluate(()=>{window.run=null;document.getElementById('agent-browser-open').click();});await frame.locator('h1').waitFor();
  const rejected=await page.evaluate(()=>{try{window.ui.openLocal('http://169.254.169.254/');return false;}catch{return true;}});assert.ok(rejected);
  assert.equal(popups,0);console.log('PASS: local app renders interactively inside Sakura, links propose in-app opening, close clears the frame, non-loopback embedding is refused, no external popup.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
