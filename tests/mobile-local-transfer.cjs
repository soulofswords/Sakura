const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});try{
 for(const saved of [false,true]){
  const page=await browser.newPage();await page.route('http://transfer.test/**',route=>route.fulfill({contentType:'text/html',body:'<body></body>'}));await page.goto('http://transfer.test/');
  await page.evaluate(saved=>{window.calls=[];window.Sakura={remembered:()=>JSON.stringify(saved?[{id:'pc-id',address:'https://192.168.1.1:8771',name:'My PC'}]:[])};window.nativeJob=async(method,...args)=>{calls.push({method,args});if(method==='requestModelTransfer')return {request_id:'transfer1'};if(method==='phoneState')return {transfer_request:{id:'transfer1',status:'ready'}};if(method==='receiveModel')return {id:'received'};return {ok:true};};},saved);
  await page.addScriptTag({content:fs.readFileSync('android/assets/local-setup.js','utf8').replace(/^import .*;\r?\n/gm,'').replace(/^export /gm,'')});
  await page.evaluate(()=>{transferSetup().then(result=>window.transferResult=result);});
  if(!saved){
   const inputs=page.locator('dialog input');await inputs.nth(0).fill('https://192.168.1.1:8771');await inputs.nth(1).fill('123456');
   await page.getByRole('button',{name:'Connect / retry',exact:true}).click();await page.getByRole('status').filter({hasText:'64-character'}).waitFor();assert.equal(await page.evaluate(()=>calls.length),0,'Missing pin never reaches native bridge');
   await inputs.nth(2).fill('a'.repeat(64));await page.getByRole('button',{name:'Connect / retry',exact:true}).click();
  }
  await page.waitForFunction(()=>window.transferResult?.id==='received');
  const calls=await page.evaluate(()=>window.calls),connect=calls.find(x=>x.method===(saved?'reconnectAsync':'connectAsync'));
  assert.deepEqual(connect.args,saved?['pc-id','https://192.168.1.1:8771']:['https://192.168.1.1:8771','123456','a'.repeat(64)]);
  assert.ok(calls.some(x=>x.method==='receiveModel'));await page.close();
 }
 console.log('PASS: Local model transfer checks new-PC pin and uses correct remembered-PC identity/address bridge arguments.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
