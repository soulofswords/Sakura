// Companion mode must offer the camera as two explicit choices: lens-style object
// recognition, or face/hand tracking layered on top of the chat companion.
const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});try{
 const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 let html=fs.readFileSync('static/index.html','utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace(/<link[^>]*rel="stylesheet"[^>]*>/g,'');
 html=html.replace('</head>','<style>'+['style.css','companion-studio.css','appearance.css'].map(f=>fs.readFileSync('static/css/'+f,'utf8')).join('\n')+'</style></head>');
 await page.route('http://camera.test/**',route=>route.fulfill({contentType:'text/html',body:html}));
 await page.goto('http://camera.test/?desktop=1&companion=1');
 await page.evaluate(()=>{document.body.className='native-renderer';window.SAKURA_EDITION='companion';
  // Same wiring app.js installs for the face-tracking options.
  const mode=document.getElementById('companion-camera-mode'),options=document.getElementById('companion-face-tracking-options');
  mode.addEventListener('change',()=>{options.hidden=mode.value!=='tracking';});});
 await page.addScriptTag({content:`(function(){${fs.readFileSync('static/js/companion-studio.js','utf8').replace(/export function/g,'function')}})()`});
 await page.waitForFunction(()=>document.body.classList.contains('companion-ui-active'));
 await page.getByRole('button',{name:'Camera & tracking',exact:true}).click();
 await page.waitForSelector('#companion-panel:not([hidden])');
 assert.equal(await page.locator('#companion-panel #companion-camera-group').count(),1,'Camera options live in the pane');
 assert.equal(await page.locator('#companion-panel #settings-tracking-camera').count(),1,'Camera picker lives in the pane');
 assert.equal(await page.locator('#companion-camera-mode').isVisible(),false,'The raw mode select is replaced by the two choices');
 const lens=page.getByRole('button',{name:/See objects/}),track=page.getByRole('button',{name:/Track my face/});
 assert.equal(await lens.isVisible(),true);assert.equal(await track.isVisible(),true);
 await lens.click();
 assert.equal(await page.locator('#companion-camera-mode').inputValue(),'objects');
 assert.equal(await page.locator('#companion-camera-enabled').isChecked(),true,'Choosing a mode enables the camera');
 assert.equal(await lens.getAttribute('aria-pressed'),'true');assert.equal(await track.getAttribute('aria-pressed'),'false');
 await track.click();
 assert.equal(await page.locator('#companion-camera-mode').inputValue(),'tracking','Choices are exclusive');
 assert.equal(await page.locator('#companion-camera-enabled').isChecked(),true);
 assert.equal(await lens.getAttribute('aria-pressed'),'false');assert.equal(await track.getAttribute('aria-pressed'),'true');
 assert.equal(await page.locator('#companion-face-tracking-options').isVisible(),true,'Tracking shows its source picker');
 await page.evaluate(()=>{window.__cameraStarts=0;document.getElementById('companion-camera-enabled').addEventListener('change',()=>window.__cameraStarts++);});
 await lens.click();
 assert.equal(await page.evaluate(()=>window.__cameraStarts),0,'Switching a running camera restarts once through the mode select');
 assert.equal(await page.locator('#companion-camera-mode').inputValue(),'objects');
 assert.equal(await page.locator('#companion-camera-enabled').isChecked(),true);
 await track.click();
 assert.equal(await page.locator('#companion-camera-enabled').isChecked(),true,'Switching to the other running choice keeps the camera on');
 await track.click();
 assert.equal(await page.locator('#companion-camera-enabled').isChecked(),false,'Choosing the running mode again stops the camera');
 assert.equal(await track.getAttribute('aria-pressed'),'false');
 await lens.click();await page.locator('#companion-camera-enabled').uncheck();
 assert.equal(await lens.getAttribute('aria-pressed'),'false','Unchecking the toggle clears both choices');
 await page.evaluate(()=>document.body.classList.add('tracking-only'));
 await page.waitForFunction(()=>!document.body.classList.contains('companion-ui-active'));
 assert.equal(await page.locator('#tab-audio #companion-camera-group').count(),1,'Leaving Companion mode returns the options to Settings');
 assert.deepEqual(errors,[]);
 console.log('PASS: Companion offers lens-style object recognition or face/hand tracking as exclusive camera choices.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
