const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const UI='https://appassets.androidplatform.net',MODEL='https://models.sakura.invalid';
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try{
  const page=await browser.newPage();
  await page.route(UI+'/**',route=>{
   const path=new URL(route.request().url()).pathname;
   if(path==='/')return route.fulfill({contentType:'text/html',body:'<body><iframe id="avatar" sandbox="allow-scripts allow-same-origin" allow="camera"></iframe><script>window.cameraPermissions=[];window.Sakura={rendererCamera:value=>cameraPermissions.push(value)};</script><script type="module">import {openRenderer} from "/avatar-channel.js";window.renderer=await openRenderer(document.getElementById("avatar"));</script></body>'});
   return route.fulfill({contentType:'text/javascript',path:'android/assets'+path});
  });
  await page.route(MODEL+'/**',route=>{
   const path=new URL(route.request().url()).pathname;
   if(path==='/local-viewer.html')return route.fulfill({contentType:'text/html',body:'<div id="model-container"></div><div id="notice"></div><script type="module" src="/phone-avatar.js"></script>'});
   if(path==='/phone-avatar.js'){
    const stub=`window.probe={loads:[],tracking:0};class ModelViewer{constructor(){this.container=document.getElementById('model-container');}setQuality(){}setVtuberTrackingMode(){}async loadModel(url){probe.loads.push(url);return true;}}class LipSync{stop(){}async playWithLipSync(){}}class AvatarTracking{stop(){}async start(){probe.tracking++;}setHandTracking(){}calibrate(){}}\n`;
    return route.fulfill({contentType:'text/javascript',body:stub+fs.readFileSync('android/assets/phone-avatar.js','utf8').replace(/^import .*;\r?\n/gm,'')});
   }
   return route.fulfill({status:404,body:''});
  });
  await page.goto(UI+'/');await page.waitForFunction(()=>!!window.renderer);
  const frame=page.frames().find(frame=>frame.url().startsWith(MODEL));assert.ok(frame);
  assert.equal(await frame.evaluate(()=>typeof window.Sakura),'undefined','Renderer has no privileged facade');
  assert.equal(await frame.evaluate(()=>{try{return !!parent.Sakura;}catch(error){return error.name;}}),'SecurityError','Cross-origin model cannot borrow the parent bridge');
  await page.evaluate(()=>renderer.load('/models/Test/model.pmx'));
  assert.deepEqual(await frame.evaluate(()=>probe.loads),['/models/Test/model.pmx'],'Rendering still loads through the restricted channel');
  await assert.rejects(page.evaluate(()=>renderer.load('https://untrusted.invalid/model.pmx')),/saved phone model/);
  await page.evaluate(()=>renderer.startTracking('user',false));
  assert.equal(await frame.evaluate(()=>probe.tracking),1);
  assert.equal(await page.evaluate(()=>cameraPermissions.at(-1)),true);
  await page.evaluate(()=>renderer.stopTracking());
  assert.equal(await page.evaluate(()=>cameraPermissions.at(-1)),false,'Stopping revokes the renderer camera lease');
  const proof=JSON.parse(fs.readFileSync('tools/android-cache/security-test/gateway-proof.json','utf8'));
  await page.evaluate(script=>{window.sakuraNativeReply=(id,result)=>window.reply=result;eval(script);},proof.invalidScript);
  assert.match(await page.evaluate(()=>reply.error),/invalid JSON/);
  assert.equal(await page.evaluate(()=>window.injected),undefined,'Raw response cannot execute');
  await page.evaluate(script=>eval(script),proof.dataScript);
  assert.equal(await page.evaluate(()=>window.injected),undefined,'Code-like text stays data');
  console.log('PASS: cross-origin model isolation, working render/track RPC, camera lease revocation, and actual Java reply scripts resist injection.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
