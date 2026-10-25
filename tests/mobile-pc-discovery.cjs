const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const ROOT=process.env.SAKURA_PHONE_ASSETS||'android/assets';
const PC={service:'sakura',id:'0f1e2d3c4b5a69788796a5b4c3d2e1f0',name:'tufa15',edition:'combined',http:'http://192.168.1.103:8771',port:8771};
const OTHER={service:'sakura',id:'11223344556677889900aabbccddeeff',name:'Living-room PC',edition:'vtuber',http:'http://192.168.1.50:8772',port:8772};
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});try{
 const page=await browser.newPage({viewport:{width:390,height:844}});
 await page.addInitScript(`
  window.__saved=[];window.__calls=[];window.__beacons=[];
  const reply=(id,value)=>setTimeout(()=>window.sakuraNativeReply?.(id,value),5);
  window.Sakura={localAvailable:()=>false,remembered:()=>JSON.stringify(window.__saved),request:()=>'{"ok":true}',
   discoverAsync:id=>reply(id,{computers:window.__beacons}),
   connectAsync:(id,address,code)=>{window.__calls.push(['connect',address,code]);
    const found=window.__beacons.find(pc=>pc.http===address);
    reply(id,code==='246810'?{token:'t',id:found?found.id:'',name:found?found.name:'Sakura',edition:found?found.edition:'companion'}:{error:'That pairing code is not valid.'});},
   reconnectAsync:(id,computer,address)=>{window.__calls.push(['reconnect',computer,address]);
    const pc=window.__saved.find(p=>p.id===computer||(computer===''&&p.address===address));
    reply(id,pc?{name:pc.name,edition:pc.edition}:{error:'Sakura was not found on this network.'});}};`);
 await page.route('http://mobile.test/**',route=>{
  const path=new URL(route.request().url()).pathname;
  if(path==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(ROOT+'/index.html','utf8')});
  const file=path.startsWith('/static/')?'static'+path.slice(7):ROOT+path;
  if(!fs.existsSync(file))return route.fulfill({status:404,body:''});
  return route.fulfill({contentType:file.endsWith('.css')?'text/css':'text/javascript',path:file});});
 await page.goto('http://mobile.test/');
 await page.evaluate(b=>{window.__beacons.push(b);},PC);

 // Choosing "Connect to PC" searches the network on its own and lists PCs by name.
 await page.click('#mode-pc');
 await page.waitForFunction(()=>document.querySelectorAll('#discovered-pcs button').length===1);
 assert.match(await page.locator('#discover-status').textContent(),/Found 1 PC running Sakura/);
 assert.ok(!(await page.locator('#discovered-pcs button').textContent()).includes('http://'),'A discovered PC is listed by name, never as a URL to type.');

 // Tapping a new PC asks only for the six-digit code.
 await page.click('#discovered-pcs button');
 assert.equal(await page.locator('#pair-code').isVisible(),true);
 assert.match(await page.locator('#pair-target').textContent(),/tufa15/);
 await page.click('#connect');
 assert.equal(await page.locator('#status').textContent(),'Enter the 6-digit code shown on your PC.');
 await page.fill('#code','111111');await page.click('#connect');
 await page.waitForFunction(()=>document.getElementById('status').textContent.includes('not valid'));

 // A second PC found on the same search pairs with its own code.
 await page.evaluate(b=>{window.__beacons.push(b);},OTHER);
 await page.click('#rescan-pcs');
 await page.waitForFunction(()=>document.querySelectorAll('#discovered-pcs button').length===2);
 await page.click('#discovered-pcs button:nth-child(2)');
 await page.fill('#code','246810');await page.click('#connect');
 await page.waitForFunction(()=>document.getElementById('controls').classList.contains('hidden')===false);
 assert.equal(await page.locator('#status').textContent(),'Connected to Living-room PC · vtuber');
 assert.deepEqual(await page.evaluate(()=>window.__calls.at(-1)),['connect',OTHER.http,'246810']);

 // A remembered PC is reconnected by its stable identity, so a moved IP needs no new code.
 await page.evaluate(id=>{window.__saved=[
  {id:id,address:'http://192.168.1.10:8771',name:'tufa15',edition:'combined',credential:'x'},
  {address:'http://192.168.1.11:8771',name:'Old desktop',edition:'companion',credential:'x'}];},PC.id);
 await page.click('#disconnect');
 await page.waitForFunction(()=>document.querySelectorAll('#saved-pcs button').length===2);
 const rows=await page.locator('#saved-pcs button').allTextContents();
 assert.ok(rows.every(row=>!row.includes('http://')),'Remembered PCs show names, not URLs.');
 await page.click('#saved-pcs button:nth-child(1)');
 await page.waitForFunction(()=>document.getElementById('controls').classList.contains('hidden')===false);
 assert.deepEqual(await page.evaluate(()=>window.__calls.at(-1)),['reconnect',PC.id,'http://192.168.1.10:8771']);
 await page.click('#disconnect');
 await page.waitForFunction(()=>document.querySelectorAll('#saved-pcs button').length===2);
 await page.click('#saved-pcs button:nth-child(2)');
 await page.waitForFunction(()=>document.getElementById('controls').classList.contains('hidden')===false);
 assert.deepEqual(await page.evaluate(()=>window.__calls.at(-1)),['reconnect','','http://192.168.1.11:8771'],'A record saved before stable identities still reconnects by address.');

 // Advanced keeps a manual host/port fallback with no scheme to type.
 await page.evaluate(()=>{window.__saved=[];window.__beacons=[];});
 await page.reload();await page.click('#mode-pc');
 await page.waitForFunction(()=>document.getElementById('discover-status').textContent.includes('No PC answered'));
 await page.click('#advanced-pair summary');
 await page.fill('#host','192.168.1');await page.fill('#manual-code','246810');await page.click('#manual-connect');
 await page.waitForFunction(()=>document.getElementById('status').textContent.includes('IPv4 address'));
 await page.fill('#host','192.168.1.77');await page.fill('#port','8772');await page.fill('#manual-code','000000');await page.click('#manual-connect');
 await page.waitForFunction(()=>window.__calls.filter(c=>c[0]==='connect').at(-1)[1]==='http://192.168.1.77:8772','A typed port is honoured.');
 await page.fill('#port','99999');await page.fill('#manual-code','246810');await page.click('#manual-connect');
 await page.waitForFunction(()=>document.getElementById('controls').classList.contains('hidden')===false);
 assert.deepEqual(await page.evaluate(()=>window.__calls.at(-1)),['connect','http://192.168.1.77:8771','246810'],'An unusable port falls back to the default.');
 const noScheme=await page.locator('#pair input,#advanced-pair input').evaluateAll(nodes=>nodes.every(i=>!/https?:\/\//.test(i.placeholder||'')));
 assert.ok(noScheme,'No phone input ever asks the user for an http:// link.');
 console.log('PASS: Wi-Fi discovery lists PCs by name, code-only pairing, identity-keyed reconnect over a stale address, and a scheme-free Advanced host/port fallback.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
