const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://local.test/**',route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/library.js')return route.fulfill({contentType:'application/javascript',body:fs.readFileSync('static/js/local-character-library.js','utf8')});
   if(url.pathname==='/static/model-library-preview.html')return route.fulfill({contentType:'text/html',body:`<script>addEventListener('message',e=>{if(e.data.type==='load')parent.postMessage({type:'model-preview',path:e.data.path,error:true},location.origin)});parent.postMessage({type:'preview-ready'},location.origin)</script>`});
   if(url.pathname==='/api/local-model-library/folder-names')return route.fulfill({json:{names:{'pmx/import-old':'Ringo'}}});
   if(url.pathname.startsWith('/api/'))return route.fulfill({status:404,body:'No preview'});
   return route.fulfill({contentType:'text/html',body:`<!doctype html><div id="model-dropdown"><button class="dropdown-trigger">PMX</button><select id="model-select" hidden><option value="pmx/Game/Helen/Helen.pmx">Helen</option><option value="pmx/Other/Irina.pmx">Irina</option><option value="pmx/import-old/Ringo.pmx">Ringo</option></select></div>
   <div id="vrm-dropdown"><button class="dropdown-trigger">VRM</button><select id="vrm-select" hidden><option value="vrm/Anna.vrm">Anna</option></select></div>
   <div id="live2d-dropdown"><button class="dropdown-trigger">Live2D</button><select id="live2d-select" hidden><option value="live2d/Annie/model.model3.json">Annie</option></select></div>
   <script>for(const select of document.querySelectorAll('select'))select.onchange=()=>window.chosen=select.value;</script><script type="module" src="/library.js"></script>`});
  });
  await page.goto('http://local.test/');
  await page.getByRole('button',{name:'PMX',exact:true}).click();
  const dialog=page.locator('#local-character-library');
  assert.equal(await dialog.isVisible(),true);
  assert.equal(await dialog.getByRole('button',{name:'Open folder Ringo',exact:true}).count(),1);
  assert.equal(await dialog.getByRole('button',{name:'Open folder import-old',exact:true}).count(),0);
  await dialog.getByRole('button',{name:'Open folder Game',exact:true}).click();
  await dialog.getByRole('button',{name:'Open folder Helen',exact:true}).click();
  assert.equal(await dialog.getByRole('button',{name:'PMX · Helen',exact:true}).count(),1);
  await dialog.getByRole('searchbox').fill('irina');
  await dialog.getByRole('button',{name:'PMX · Irina',exact:true}).click();
  assert.equal(await page.evaluate(()=>window.chosen),'pmx/Other/Irina.pmx');
  assert.equal(await dialog.isVisible(),false);
  await page.getByRole('button',{name:'VRM',exact:true}).click();
  assert.equal(await dialog.getByRole('button',{name:'VRM · Anna',exact:true}).count(),1);
  await dialog.getByRole('button',{name:'Close character library'}).click();
  await page.getByRole('button',{name:'Live2D',exact:true}).click();
  await dialog.getByRole('button',{name:'Open folder Annie',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[data-local-model]')?.textContent==='Annie');
  await dialog.getByRole('button',{name:'Live2D · Annie',exact:true}).click();
  assert.equal(await page.evaluate(()=>window.chosen),'live2d/Annie/model.model3.json');
  assert.deepEqual(errors,[]);
  console.log('PASS: separate format buttons, folder navigation, cross-folder search, preview fallback, and real selector change events.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
