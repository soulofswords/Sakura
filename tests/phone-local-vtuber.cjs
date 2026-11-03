const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});try{
 const page=await browser.newPage({viewport:{width:390,height:844}});
 await page.route('https://models.sakura.invalid/**',route=>route.fulfill({contentType:'text/html',body:`<script>window.addEventListener('message',event=>{if(event.origin!=='http://phone.test'||event.source!==parent)return;const d=event.data;if(d.type==='avatar-ping')parent.postMessage({type:'avatar-ready'},event.origin);if(d.type==='avatar-call'){const labels={startTracking:'start',stopTracking:'stop',calibrate:'calibrate',hands:'hands:'+d.args[0]};if(labels[d.method])parent.postMessage({type:'probe-call',value:labels[d.method]},event.origin);if(d.id)parent.postMessage({type:'avatar-reply',id:d.id,result:null},event.origin);}});</script>`}));
 await page.route('http://phone.test/**',route=>{const path=new URL(route.request().url()).pathname;if(path==='/local-viewer.html')return route.fulfill({contentType:'text/html',body:`<script>window.phoneAvatar={load:async()=>{},pause:()=>{},startTracking:async()=>{parent.calls.push('start')},stopTracking:()=>parent.calls.push('stop'),calibrate:()=>parent.calls.push('calibrate'),hands:on=>parent.calls.push('hands:'+on)};</script>`});if(path==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync('android/assets/index.html','utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'')});return route.fulfill({status:404,body:''});});
 await page.goto('http://phone.test/');await page.evaluate(()=>{
  window.calls=[];window.saved=[{id:'one',name:'My VRM',format:'vrm',url:'/models/one/model.vrm'}];
  window.Sakura={localModels:()=>JSON.stringify(saved),rendererCamera:()=>{}};
  window.addEventListener('message',event=>{if(event.origin==='https://models.sakura.invalid'&&event.data?.type==='probe-call')calls.push(event.data.value);});
  window.nativeJob=async method=>{calls.push(method);if(method==='importPhoneModel'){const model={id:'two',name:'Imported PMX',format:'pmx',url:'/models/two/main.pmx'};saved.push(model);return model;}if(method==='requestModelTransfer')return {request_id:'transfer'};if(method==='phoneState')return {transfer_request:{id:'transfer',status:'ready'}};if(method==='receiveModel')return saved[0];};
  window.sakuraEnsurePc=async()=>calls.push('pc-reconnect');
 });
 await page.addScriptTag({content:fs.readFileSync('android/assets/avatar-channel.js','utf8').replace(/^export /gm,'')});
 await page.addScriptTag({content:fs.readFileSync('android/assets/phone-vtuber.js','utf8').replace(/^import .*;\r?\n/gm,'')});
 await page.click('#mode-phone-vtuber');assert.equal(await page.locator('#phone-vtuber-mode').isVisible(),true);assert.equal(await page.locator('#local-mode').isVisible(),false);
 await page.click('#phone-model-load');await page.waitForFunction(()=>document.getElementById('phone-local-tracking-status').textContent.includes('ready'));
 await page.click('#phone-local-tracking');assert.equal(await page.locator('#phone-local-tracking').getAttribute('aria-pressed'),'true');
 await page.check('#phone-local-hands');await page.click('#phone-local-calibrate');
 await page.waitForFunction(()=>calls.includes('hands:true')&&calls.includes('calibrate'));
 assert.equal(await page.evaluate(()=>calls.includes('pc-reconnect')),false,'Standalone tracking never reconnects to a PC');
 await page.click('#phone-local-tracking');assert.equal(await page.locator('#phone-local-tracking').getAttribute('aria-pressed'),'false');
 await page.click('#phone-model-import');await page.waitForFunction(()=>document.getElementById('phone-model-list').value==='two');
 await page.click('#phone-model-pc');await page.waitForFunction(()=>calls.includes('receiveModel'));
 await page.click('#change-mode');assert.equal(await page.locator('#phone-vtuber-mode').isVisible(),false);
 assert.ok(await page.evaluate(()=>calls.includes('stop')));
 console.log('PASS: offline phone VTuber, local import, paired-PC import, hand toggle, calibration, start/stop and exit cleanup; no AI setup required.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
