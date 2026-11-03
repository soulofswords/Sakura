// Both studio shells port the same toolbar controls. Switching between them must
// hand the controls over, not leave them stranded in the hidden toolbar.
const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const SHELLS=['vtuber-studio.js','companion-studio.js'];
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});try{
 const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 let html=fs.readFileSync('static/index.html','utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace(/<link[^>]*rel="stylesheet"[^>]*>/g,'');
 html=html.replace('</head>','<style>'+['style.css','vtuber-studio.css','companion-studio.css','appearance.css'].map(f=>fs.readFileSync('static/css/'+f,'utf8')).join('\n')+'</style></head>');
 await page.route('http://handover.test/**',route=>route.fulfill({contentType:'text/html',body:html}));
 await page.goto('http://handover.test/?desktop=1&companion=1');
 await page.evaluate(()=>{document.body.className='native-renderer';window.SAKURA_EDITION='companion';});
 // Each shell is an ES module with its own top-level ICONS, so install them in
 // separate scopes the way the browser would.
 for(const file of SHELLS)await page.addScriptTag({content:`(function(){${fs.readFileSync('static/js/'+file,'utf8').replace(/^import \{installSpeakerEnrolment\}[^\n]*$/m,fs.readFileSync('static/js/speaker-enrolment.js','utf8').replace('export function','function')).replace(/export function/g,'function')}})()`});
 const ids=['model-dropdown','vrm-dropdown','live2d-dropdown','upload-pmx-toolbar','upload-vrm-toolbar','upload-live2d-toolbar','full-model-btn','obs-background-enabled','mmd-btn'];
 const home=async()=>page.evaluate(names=>Object.fromEntries(names.map(id=>{
  const el=document.getElementById(id);
  return [id,el?.closest('#companion-studio')?'companion':el?.closest('#vtuber-studio')?'vtuber':el?.closest('#companion-toolbar')?'toolbar':el?'other':'missing'];
 })),ids);
 const openModels=async pane=>{const [body,panel]=pane==='vtuber'?['studio-ui-active','studio-panel']:['companion-ui-active','companion-panel'];
  await page.waitForFunction(p=>document.body.classList.contains(p),body);
  await page.getByRole('button',{name:'Models',exact:true}).click();await page.waitForSelector(`#${panel}:not([hidden])`);};
 await openModels('companion');
 assert.deepEqual(await home(),Object.fromEntries(ids.map(id=>[id,'companion'])),'Companion starts with the model controls in its own panel');
 await page.evaluate(()=>document.body.classList.add('tracking-only'));
 await openModels('vtuber');
 assert.deepEqual(await home(),Object.fromEntries(ids.map(id=>[id,'vtuber'])),'Switching to VTuber keeps the controls in the studio panel');
 assert.deepEqual(await page.evaluate(()=>Object.fromEntries([...document.querySelectorAll('#vtuber-studio [data-studio-port]')].map(p=>[p.dataset.studioPort,p.children.length]))['model-dropdown']),1,'PMX selector is in its port');
 assert.equal(await page.evaluate(()=>document.querySelector('#vtuber-studio [data-studio-port="imports"]').children.length),4,'PMX, VRM, Live2D and rescan buttons are in the import port');
 assert.equal(await page.locator('#studio-panel #model-dropdown').isVisible(),true,'PMX selector is visible in the studio panel');
 assert.equal(await page.locator('#studio-panel #vrm-dropdown').isVisible(),true,'VRM selector is visible in the studio panel');
 assert.equal(await page.locator('#studio-panel #live2d-dropdown').isVisible(),true,'Live2D selector is visible in the studio panel');
 assert.equal(await page.locator('#studio-panel #studio-model-search').isVisible(),true,'Character search stays in the studio panel');
 await page.evaluate(()=>document.body.classList.remove('tracking-only'));
 await openModels('companion');
 assert.deepEqual(await home(),Object.fromEntries(ids.map(id=>[id,'companion'])),'Returning to Companion reclaims the controls');
 await page.evaluate(()=>document.body.classList.add('tracking-only'));
 await openModels('vtuber');
 assert.deepEqual(await home(),Object.fromEntries(ids.map(id=>[id,'vtuber'])),'A second switch to VTuber still shows the controls');
 assert.equal(await page.evaluate(()=>document.querySelectorAll('#companion-toolbar .custom-dropdown,#companion-toolbar #upload-pmx-toolbar').length),0,'Nothing is stranded in the hidden toolbar');
 assert.deepEqual(errors,[],'Handing controls over never throws');
 console.log('PASS: PMX/VRM/Live2D selectors and upload buttons survive repeated Companion <-> VTuber handovers.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
