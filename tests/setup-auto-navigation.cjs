const fs=require('node:fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{
 const guide=fs.readFileSync('static/js/first-run-guide.js','utf8');
 for(const edition of ['companion','vtuber']){
  const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const html=fs.readFileSync('static/index.html','utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace(/<link[^>]*rel="stylesheet"[^>]*>/g,'');
  await page.route('http://tour.test/**',r=>{const path=new URL(r.request().url()).pathname;if(path.startsWith('/api/'))return r.fulfill({json:{conversation_mode:'friend',delivery_spice:'mild'}});if(path.startsWith('/static/assets/')&&fs.existsSync('.'+path))return r.fulfill({contentType:path.endsWith('.svg')?'image/svg+xml':'image/png',body:fs.readFileSync('.'+path)});return r.fulfill({contentType:'text/html',body:html});});
  await page.goto('http://tour.test/');
  await page.addStyleTag({content:['style.css','companion-studio.css','vtuber-studio.css','studio-polish.css','appearance.css'].map(f=>fs.readFileSync('static/css/'+f,'utf8')).join('\n')});
  await page.evaluate(({edition,theme})=>{
   window.SAKURA_EDITION=edition;document.documentElement.dataset.uiTheme=theme;document.body.className='native-renderer native-library'+(edition==='vtuber'?' tracking-only':'');
   for(const [button,panel] of [['settings-btn','settings-modal'],['expression-editor-btn','expression-modal'],['tracking-mode-btn','tracking-modal']])document.getElementById(button).onclick=()=>document.getElementById(panel).classList.toggle('hidden');
   for(const [button,panel] of [['close-settings-btn','settings-modal'],['close-expression-modal','expression-modal'],['close-tracking-modal','tracking-modal']])document.getElementById(button).onclick=()=>document.getElementById(panel).classList.add('hidden');
   for(const tab of document.querySelectorAll('#settings-modal [data-tab]'))tab.onclick=()=>{for(const b of document.querySelectorAll('#settings-modal [data-tab]'))b.classList.toggle('active',b===tab);for(const p of document.querySelectorAll('#settings-modal .tab-content'))p.classList.toggle('active',p.id==='tab-'+tab.dataset.tab);};
  },{edition,theme:process.env.SAKURA_AUDIT_THEME||'dark'});
  await page.addScriptTag({content:fs.readFileSync('static/js/'+(edition==='companion'?'companion-studio.js':'vtuber-studio.js'),'utf8').replace(/^import \{installSpeakerEnrolment\}[^\n]*$/m,fs.readFileSync('static/js/speaker-enrolment.js','utf8').replace('export function','function')).replace('export function','function')});
  await page.addScriptTag({content:guide});const dialog=page.locator('#sakura-setup-guide');await dialog.waitFor({state:'visible'});
  await dialog.locator('.setup-next').click();
  const modelPanel=page.locator(edition==='companion'?'[data-companion-content="character"]':'[data-studio-content="models"]');await modelPanel.waitFor({state:'visible'});
  await dialog.locator('.setup-show').click();assert.equal(await modelPanel.isVisible(),true,'Repeated Show must not close the selected pane');
  if(edition==='companion'){await dialog.locator('.setup-next').click();await page.locator('[data-companion-content="voice"]').waitFor({state:'visible'});}
  await dialog.locator('.setup-next').click();await page.locator(edition==='companion'?'[data-companion-content="camera"]':'#tracking-modal').waitFor({state:'visible'});
  assert.equal(await dialog.isVisible(),true,'Automatic camera navigation leaves guide open and never starts a camera');
  await dialog.locator('.setup-next').click();await page.locator('#settings-modal').waitFor({state:'visible'});assert.equal(await page.locator('#sakura-setup-focus').isVisible(),true,'Highlight the visible Settings dock button, not the hidden legacy toolbar button');
  await dialog.locator('.setup-show').click();assert.equal(await page.locator('#settings-modal').isVisible(),true,'Repeated Show keeps Settings open');
  if(process.env.SAKURA_AUDIT_SCREENSHOTS){const directory='audit-results/ui-button-routing-2026-11-03';fs.mkdirSync(directory,{recursive:true});await page.screenshot({path:directory+'/'+edition+'-guide-settings'+(process.env.SAKURA_AUDIT_THEME?'-'+process.env.SAKURA_AUDIT_THEME:'')+'.png'});}
  await dialog.locator('.setup-back').click();await page.locator(edition==='companion'?'[data-companion-content="camera"]':'#tracking-modal').waitFor({state:'visible'});
  assert.deepEqual(errors,[]);await page.close();
 }
 const page=await browser.newPage();await page.route('http://agent-tour.test/',r=>r.fulfill({contentType:'text/html',body:'<title>Sakura Agent</title><nav id="agent-studio-nav"><button aria-label="Tasks">Tasks</button><button aria-label="Connections">Connections</button></nav><details id="agent-task-options"><input id="planner-provider"><input id="workspace"></details><div id="connections"></div><div id="agent-metrics"></div><script>window.visits=[];document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>visits.push(b.textContent));</script>'}));
 await page.goto('http://agent-tour.test/');await page.addScriptTag({content:guide});await page.locator('#sakura-setup-guide').waitFor({state:'visible'});await page.locator('.setup-next').click();assert.equal(await page.locator('#agent-task-options').getAttribute('open'),'');assert.deepEqual(await page.evaluate(()=>visits),['Tasks']);
 await page.locator('[aria-label="Step 5: Connect only what you need"]').click();assert.equal(await page.evaluate(()=>visits.at(-1)),'Connections');
 console.log('PASS: Next/Back/step navigation automatically opens Companion, VTuber and Agent panels; repeated navigation never toggles them closed.');
}finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
