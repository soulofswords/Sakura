const fs=require('fs');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try {
  const page=await browser.newPage(); await page.emulateMedia({colorScheme:'light'});
  await page.route('http://sakura.test/**',route=>route.fulfill({contentType:'text/html',body:'<body class="tracking-only studio-ui-active"><div id="theme-popover"><div class="popover-header"><span>Old theme</span></div><div class="popover-body"><input type="color"></div></div><div class="modal-card"><div id="tab-theme"><button>Old color</button></div></div><div id="studio-panel"><div class="studio-card"><h3>Models</h3></div></div></body>'}));
  await page.goto('http://sakura.test/');
  await page.addStyleTag({content:fs.readFileSync('static/css/vtuber-studio.css','utf8')+'\n'+fs.readFileSync('static/css/appearance.css','utf8')});
  const script=fs.readFileSync('static/js/appearance.js','utf8').replace('export function','function');await page.addScriptTag({content:script});
  assert.deepEqual(await page.locator('#tab-theme [data-appearance-select] option').allTextContents(),['Light','Dark','System']);
  assert.equal(await page.locator('#tab-theme input[type=color],#theme-popover input[type=color]').count(),0);
  assert.equal(await page.locator('#legacy-lighting-controls').count(),0,'Legacy theme controls are removed, not hidden');
  assert.equal(await page.locator('input[type=color]').count(),0);
  assert.equal(await page.locator('html').getAttribute('data-ui-theme'),'light');
  await page.locator('#tab-theme [data-appearance-select]').selectOption('dark');
  assert.equal(await page.locator('html').getAttribute('data-ui-theme'),'dark');
  assert.equal(await page.locator('#theme-popover select').inputValue(),'dark');
  assert.equal(await page.locator('.studio-card').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(32, 36, 43)');
  assert.equal(await page.evaluate(()=>localStorage.getItem('sakura_ui_theme')),'dark');
  await page.emulateMedia({colorScheme:'light'}); assert.equal(await page.locator('html').getAttribute('data-ui-theme'),'dark');
  await page.locator('#theme-popover select').selectOption('system');
  assert.equal(await page.locator('html').getAttribute('data-ui-theme'),'light');
  await page.emulateMedia({colorScheme:'dark'}); await page.waitForFunction(()=>document.documentElement.dataset.uiTheme==='dark');
  await page.reload();await page.addScriptTag({content:script});assert.equal(await page.locator('#tab-theme [data-appearance-select]').inputValue(),'system');
  console.log('PASS: exactly three themes, synchronized selectors, readable dark cards, saved choice, and live system appearance changes.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
