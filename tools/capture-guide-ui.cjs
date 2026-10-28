// Capture actual UI components with local demo state; no personal models/accounts.
const fs=require('fs'),path=require('path'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});try{
 const out=path.resolve('docs/user-guides/images');fs.mkdirSync(out,{recursive:true});
 for(const edition of ['companion','vtuber']){
  const page=await browser.newPage({viewport:{width:1366,height:900},deviceScaleFactor:1});
  let html=fs.readFileSync('static/index.html','utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace(/<link[^>]*rel="stylesheet"[^>]*>/g,'');
  html=html.replace('</head>','<style>'+['style.css','vtuber-studio.css','companion-studio.css','appearance.css'].map(f=>fs.readFileSync('static/css/'+f,'utf8')).join('\n')+'</style></head>');
  await page.route('http://127.0.0.1:9987/**',route=>{const p=new URL(route.request().url()).pathname;if(p.startsWith('/static/assets/')&&p.endsWith('.png'))return route.fulfill({contentType:'image/png',body:fs.readFileSync('.'+p)});if(p==='/api/version')return route.fulfill({json:{version:'1.0.1',product:edition==='vtuber'?'Sakura VTuber':'Sakura Companion'}});if(p.startsWith('/api/'))return route.fulfill({json:{models:[],live2d_models:[],ui_theme:'dark',conversation_mode:'friend'}});return route.fulfill({contentType:'text/html',body:html});});
  await page.goto('http://127.0.0.1:9987/');await page.evaluate(e=>{window.SAKURA_EDITION=e;document.querySelector('#top-bar .badge')?.replaceChildren(document.createTextNode(e==='vtuber'?'VTuber':'Companion'));if(e==='vtuber')document.getElementById('app-brand-logo').src='/static/assets/vtuber-app.png';localStorage.setItem('sakura_ui_theme','dark');document.documentElement.className='';document.body.className='native-library native-renderer';
   for(const [id,modal]of [['settings-btn','settings-modal'],['tracking-mode-btn','tracking-modal'],['expression-editor-btn','expression-modal']])document.getElementById(id).onclick=()=>document.getElementById(modal).classList.remove('hidden');
   for(const b of document.querySelectorAll('#settings-modal .tab-btn'))b.onclick=()=>{for(const t of document.querySelectorAll('#settings-modal .tab-btn'))t.classList.toggle('active',t===b);for(const p of document.querySelectorAll('#settings-modal .tab-content'))p.classList.toggle('active',p.id==='tab-'+b.dataset.tab);};
   for(const [id,modal]of [['close-settings-btn','settings-modal'],['close-tracking-modal','tracking-modal'],['close-expression-modal','expression-modal']])document.getElementById(id).onclick=()=>document.getElementById(modal).classList.add('hidden');
   window.viewer={container:document.getElementById('viewer'),scene:{},renderer:{domElement:document.createElement('canvas')}};
   const note=document.createElement('p');note.textContent='Sakura 1.0.1 · UI demonstration · Import your own character';note.style.cssText='position:fixed;left:110px;top:140px;color:#94a3b8;font:18px system-ui;max-width:360px';document.body.append(note);
  },edition);
  for(const script of ['appearance.js','vtuber-studio.js','companion-studio.js'])await page.addScriptTag({content:'{\n'+fs.readFileSync('static/js/'+script,'utf8').replace('export function','function')+'\n}'});
  await page.addScriptTag({content:fs.readFileSync('static/js/pmx-stage.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export class','class')+';window.scenery=new PmxStage(viewer);'});
  if(edition==='vtuber')await page.evaluate(()=>document.body.classList.add('tracking-only'));
  await page.waitForTimeout(200);
  const prefix=edition==='vtuber'?'data-studio-pane':'data-companion-pane';
  await page.locator(`[${prefix}="${edition==='vtuber'?'models':'character'}"]`).click();await page.screenshot({path:path.join(out,edition+'-models.png')});
  await page.locator(`[${prefix}="settings"]`).click();await page.locator('#settings-modal [data-tab="theme"]').click();await page.evaluate(()=>{for(const tab of document.querySelectorAll('#settings-modal .tab-btn'))tab.classList.toggle('active',tab.dataset.tab==='theme');});await page.waitForFunction(()=>document.getElementById('sakura-version').textContent.includes('1.0.1'));await page.locator('#open-graphics-settings').click();await page.screenshot({path:path.join(out,edition+'-settings.png')});
  if(edition==='companion')await page.locator('[data-companion-pane="memory"]').click();
  await page.locator(`[${prefix}="background"]`).click();await page.locator('#pmx-stage-enabled').check();await page.locator('#pmx-stage-card').evaluate(el=>el.scrollIntoView({block:'start'}));await page.mouse.move(700,40);await page.screenshot({path:path.join(out,edition+'-scenery.png')});
  await page.close();
 }
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
