// Desktop WebView smoke test. Native bridge is mocked; no camera or real API is used.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const assetRoot=process.env.SAKURA_MOBILE_APK_ASSETS?path.resolve(process.env.SAKURA_MOBILE_APK_ASSETS):null;
function find(dir,predicate){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){const file=path.join(dir,entry.name);if(entry.isFile()&&predicate(file))return file;if(entry.isDirectory()){const result=find(file,predicate);if(result)return result;}}}
const selected=[['pmx',find(path.join(root,'models'),p=>/Ringo\.pmx$/i.test(p))],['vrm',find(path.join(root,'models'),p=>/\.vrm$/i.test(p))],['live2d',find(path.join(root,'models/live2d'),p=>/miu2022\.model3\.json$/i.test(p))]];
const models=selected.filter(([,p])=>p).map(([format,p])=>({id:format,format,name:path.basename(p),url:'/models/'+path.relative(path.join(root,'models'),p).split(path.sep).join('/')}));
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=d3d11']});
 try{
  const page=await browser.newPage({viewport:{width:430,height:900},hasTouch:true}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('http://phone.test/**',async route=>{
   const url=new URL(route.request().url()),urlpath=decodeURIComponent(url.pathname);let file;
   if(urlpath==='/api/mobile/transfer-status'&&route.request().method()==='GET')return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({request:{id:'desktop-test',status:'received'}})});
   if(urlpath.startsWith('/api/'))return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({repairs:null})});
   if(urlpath.startsWith('/models/'))file=path.join(root,urlpath.slice(1));
   else if(assetRoot)file=path.join(assetRoot,urlpath==='/'?'index.html':urlpath.slice(1));
   else if(urlpath.startsWith('/static/'))file=path.join(root,urlpath.slice(1));
   else file=path.join(root,'android/assets',urlpath==='/'?'index.html':urlpath.slice(1));
   if(!(file.startsWith(root+path.sep)||(assetRoot&&file.startsWith(assetRoot+path.sep)))||!fs.existsSync(file)||!fs.statSync(file).isFile())return route.fulfill({status:404,body:''});
   const ext=path.extname(file).toLowerCase(),mime={'.js':'application/javascript','.html':'text/html','.json':'application/json','.wasm':'application/wasm','.png':'image/png','.jpg':'image/jpeg'}[ext]||'application/octet-stream';
   await route.fulfill({contentType:mime,body:fs.readFileSync(file)});
  });
  await page.addInitScript(({models})=>{
   let config={provider:'gemini',model:'gemini-flash-latest',voice:'female',address:'sir',key_set:!localStorage.getItem('test-empty')};window.testCalls=[];
   let savedModels=localStorage.getItem('test-empty')?[]:models,transferPolls=0;
   window.Sakura={localAvailable:()=>true,localConfig:()=>JSON.stringify(config),
    configureLocal:(provider,key,model,voice,address)=>{config={provider,model,voice,address,key_set:true};testCalls.push({type:'config',voice});return JSON.stringify(config);},
    remembered:()=>JSON.stringify([{name:'Saved PC',address:'http://192.168.1.10:8771'}]),
    reconnectAsync:id=>{testCalls.push({type:'reconnect'});const fail=window.failNextReconnect;window.failNextReconnect=false;setTimeout(()=>window.sakuraNativeReply(id,fail?{error:'PC offline (test)'}:{name:'Saved PC',edition:'companion'}),10);},
    localModels:()=>JSON.stringify(savedModels),
    request:()=>JSON.stringify({expressions:['Smile']}),
    localChat:(id,history)=>{testCalls.push({type:'chat',history:JSON.parse(history)});setTimeout(()=>window.sakuraNativeReply(id,{reply:'Hello. How can I help?'}),10);},
    localSpeak:id=>setTimeout(()=>window.sakuraNativeReply(id,{error:'Test provider voice unavailable'}),10),
    modelCatalog:id=>setTimeout(()=>window.sakuraNativeReply(id,{provider:config.provider,models:['gemini-test-flash','gemini-test-pro']}),10),
    checkLocalApi:id=>setTimeout(()=>window.sakuraNativeReply(id,{ok:true,message:'API test Passed · test model accepted a generation request.'}),10),
    requestModelTransfer:id=>{testCalls.push({type:'request-model'});transferPolls=0;setTimeout(()=>window.sakuraNativeReply(id,{request_id:'test-request'}),10);},
    phoneState:id=>{transferPolls++;setTimeout(()=>window.sakuraNativeReply(id,{transfer_request:{id:'test-request',status:transferPolls>1?'ready':'waiting'}}),10);},
    receiveModel:id=>{savedModels=[models[0]];testCalls.push({type:'receive'});setTimeout(()=>window.sakuraNativeReply(id,models[0]),10);},
   };
  },{models});
  await page.goto('http://phone.test/index.html');
  await page.locator('#app-modes').waitFor({state:'visible'});
  assert.equal(await page.locator('#pc-mode').isVisible(),false);
  assert.equal(await page.locator('#local-mode').isVisible(),false);
  await page.waitForTimeout(250);
  assert.equal(await page.evaluate(()=>testCalls.filter(x=>x.type==='reconnect').length),0,'Opening the app must not connect to PC');
  await page.click('#mode-local');await page.locator('#local-mode').waitFor({state:'visible'});
  assert.equal(await page.locator('#sakura-button-feedback-style').count(),1,'Global button feedback installed');
  assert.equal(await page.evaluate(()=>{const button=document.createElement('button');document.body.append(button);button.click();const animation=getComputedStyle(button).animationName;button.remove();return animation;}),'sakura-button-tap','Dynamically created buttons receive click animation');
  await page.getByRole('button',{name:'Use model',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('#local-send').disabled);
  await page.waitForTimeout(250);
  assert.equal(await page.evaluate(()=>testCalls.filter(x=>x.type==='reconnect').length),0,'Local must work without attempting a PC connection');
  await page.click('summary');await page.selectOption('#local-voice','male');
  await page.waitForFunction(()=>document.querySelector('#local-status').textContent==='Saved · Male voice');
  await page.selectOption('#local-voice','female');
  await page.waitForFunction(()=>document.querySelector('#local-status').textContent==='Saved · Female voice');
  await page.getByRole('button',{name:'Find available models',exact:true}).click();
  await page.getByRole('combobox',{name:'Available chat models'}).waitFor({state:'visible'});
  await page.getByRole('combobox',{name:'Available chat models'}).selectOption('gemini-test-pro');
  assert.equal(await page.locator('#local-model-id').inputValue(),'gemini-test-pro');
  await page.getByRole('button',{name:'Test API (small request)',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#local-status').textContent.includes('API test Passed'));
  await page.uncheck('#local-speech');await page.fill('#local-message','Hello');await page.click('#local-send');
  await page.waitForFunction(()=>document.querySelector('#local-conversation').textContent.includes('Hello. How can I help?'));
  await page.fill('#local-message','Remember my last message?');await page.click('#local-send');
  await page.waitForFunction(()=>window.testCalls.filter(x=>x.type==='chat').length===2);
  assert.equal(await page.evaluate(()=>testCalls.filter(x=>x.type==='chat')[1].history.length),3);
  await page.waitForFunction(()=>!document.querySelector('#local-send').disabled);
  await page.evaluate(()=>window.sakuraCallState(true));assert.equal(await page.locator('#local-send').isDisabled(),true);
  await page.evaluate(()=>window.sakuraCallState(false));assert.equal(await page.locator('#local-send').isDisabled(),false);
  const reports=[];
  for(const model of models){
   await page.selectOption('#local-format',model.format);await page.selectOption('#local-models',model.id);
   await page.waitForFunction(name=>document.querySelector('#local-status').textContent.startsWith(name+' · '),model.name,{timeout:90000});
   const frame=page.frames().find(frame=>frame.url().includes('local-viewer.html'));
   await frame.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
   reports.push(await frame.evaluate(()=>{const canvases=[...document.querySelectorAll('canvas')];let visible=0;for(const canvas of canvases){const gl=canvas.getContext('webgl2')||canvas.getContext('webgl');if(!gl)continue;gl.finish();const pixels=new Uint8Array(gl.drawingBufferWidth*gl.drawingBufferHeight*4);gl.readPixels(0,0,gl.drawingBufferWidth,gl.drawingBufferHeight,gl.RGBA,gl.UNSIGNED_BYTE,pixels);for(let i=3;i<pixels.length;i+=4)if(pixels[i]>20)visible++;if(gl.getError())throw Error('WebGL error in mobile viewer');}return {canvasCount:canvases.length,visible,width:innerWidth,height:innerHeight,notice:document.querySelector('#notice').textContent};}));
   assert.ok(reports.at(-1).canvasCount>0);
   assert.ok(reports.at(-1).visible>100,JSON.stringify(reports.at(-1)));
   if(model.format==='live2d'){
    await page.locator('#local-avatar').scrollIntoViewIfNeeded();const bounds=await page.locator('#local-avatar').boundingBox();
    const before=await frame.evaluate(()=>Number(localStorage.getItem('sakura_model_size')||100));
    const cdp=await page.context().newCDPSession(page),cx=bounds.x+bounds.width/2,cy=bounds.y+bounds.height/2;
    const touches=distance=>[{id:1,x:cx-distance,y:cy,radiusX:3,radiusY:3,force:1},{id:2,x:cx+distance,y:cy,radiusX:3,radiusY:3,force:1}];
    await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:touches(35)});
    await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:touches(70)});
    await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    const after=await frame.evaluate(()=>Number(localStorage.getItem('sakura_model_size')||100));assert.ok(after>before*1.5,JSON.stringify({before,after}));
    await cdp.detach();
   }
  }
  assert.equal(await page.evaluate(()=>testCalls.filter(x=>x.type==='reconnect').length),0,'Chat and saved model loading must not contact PC');
  await page.click('#change-mode');assert.equal(await page.locator('#local-avatar').getAttribute('src'),'about:blank');
  await page.click('#mode-pc');await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Connected'));
  assert.equal(await page.evaluate(()=>testCalls.filter(x=>x.type==='reconnect').length),1,'PC mode reconnects to saved PC');
  await page.click('#change-mode');await page.click('#mode-local');await page.locator('#local-mode').waitFor({state:'visible'});
  await page.getByRole('button',{name:'Use model',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#local-send').disabled);
  await page.reload();await page.locator('#app-modes').waitFor({state:'visible'});
  assert.equal(await page.locator('#pc-mode').isVisible(),false);
  await page.click('#mode-local');await page.locator('#local-mode').waitFor({state:'visible'});
  await page.getByRole('button',{name:'Use model',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#local-send').disabled);
  await page.waitForFunction(()=>document.querySelector('#local-conversation').textContent.includes('Remember my last message?'));
  // First setup: no models means no assistant access until API setup and a successful transfer.
  await page.evaluate(()=>localStorage.setItem('test-empty','1'));await page.reload();await page.click('#mode-local');
  await page.getByRole('heading',{name:'1 · Choose your AI provider'}).waitFor();
  assert.equal(await page.locator('#local-send').isDisabled(),true);
  assert.equal(await page.evaluate(()=>testCalls.filter(x=>x.type==='reconnect').length),0);
  await page.locator('dialog input[type="password"]').fill('test-key-not-real');
  await page.getByRole('button',{name:'Find available models',exact:true}).click();
  await page.getByRole('combobox',{name:'Available chat models'}).waitFor({state:'visible'});
  assert.equal(await page.locator('dialog input[type="password"]').inputValue(),'','Key is cleared after secure native saving');
  await page.getByRole('button',{name:'Save and continue'}).click();
  await page.getByRole('heading',{name:'2 · Connect to PC for model transfer'}).waitFor();
  await page.waitForFunction(()=>document.querySelector('dialog')?.textContent.includes('Connection Passed'));
  await page.waitForFunction(()=>!document.querySelector('dialog')&&!document.querySelector('#local-send').disabled,{timeout:90000});
  assert.equal(await page.evaluate(()=>testCalls.filter(x=>x.type==='request-model').length),1);
  assert.equal(await page.evaluate(()=>testCalls.filter(x=>x.type==='receive').length),1);
  assert.equal(await page.evaluate(()=>testCalls.filter(x=>x.type==='reconnect').length),1);
  await page.evaluate(()=>window.failNextReconnect=true);
  await page.locator('#local-mode details').evaluate(element=>element.open=true);
  await page.click('#local-choose-model');await page.getByRole('button',{name:'Add model',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('dialog')?.textContent.includes('Failed'));
  assert.equal(await page.getByRole('heading',{name:'1 · Choose your AI provider'}).count(),0,'Existing phone model skips API setup');
  await page.getByRole('button',{name:'Connect / retry',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('dialog')&&!document.querySelector('#local-send').disabled);
  // The desktop side opens its type picker automatically, then the selected package is sent.
  await page.evaluate(async()=>{
   window.desktopSelections=[];window.desktopReports=[];
   window.pywebview={api:{show_phone_transfer:async()=>true,
    choose_mobile_model_package:async kind=>{desktopSelections.push(kind);return {selection:'chosen',entries:['nested/model.pmx','nested/variant.pmx'],folder:'Entire model folder',format:kind};},
    send_mobile_model_package:async(selection,index,requestId)=>{desktopReports.push({selection,index,requestId});return {model:{name:'Test model'}};}}};
   const {openMobileModelTransfer}=await import('/static/js/mobile-model-transfer.js');await openMobileModelTransfer('desktop-test');
  });
  await page.getByRole('button',{name:'PMX folder',exact:true}).click();
  await page.locator('#mobile-model-transfer-dialog select').selectOption('1');
  await page.evaluate(()=>{
   const original=pywebview.api.send_mobile_model_package;pywebview.api.send_mobile_model_package=async(...args)=>{await new Promise(resolve=>setTimeout(resolve,200));return original(...args);};
  });
  await page.getByRole('button',{name:'Send selected model',exact:true}).click();
  await page.getByRole('button',{name:'Preparing model…',exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Preparing model…',exact:true}).getAttribute('aria-busy'),'true');
  await page.waitForFunction(()=>window.desktopReports.length===1);
  assert.deepEqual(await page.evaluate(()=>desktopSelections),['pmx']);
  assert.deepEqual(await page.evaluate(()=>desktopReports[0]),{selection:'chosen',index:1,requestId:'desktop-test'});
  await page.getByRole('button',{name:'Sent ✓',exact:true}).waitFor();
  await page.getByRole('button',{name:'Close',exact:true}).click();
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(root,'audit-results/mobile-local-webview.json'),JSON.stringify({models:models.map(x=>({name:x.name,format:x.format})),reports,errors,nativeBridge:'mocked; physical Android call and network testing required'},null,2));
  console.log('PASS: mobile setup, voice selection, saved chat, call mute gating, PMX/VRM/Live2D rendering, real two-finger Live2D pinch, global button animations and transfer preparing/sent feedback');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
