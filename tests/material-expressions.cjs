const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});try{
 const page=await browser.newPage();await page.route('http://127.0.0.1:9989/**',r=>r.fulfill({contentType:'text/html',body:'<section data-model-panel="expression"></section><button id="model-color-reset"></button>'}));await page.goto('http://127.0.0.1:9989/');
 await page.addScriptTag({content:fs.readFileSync('static/js/part-appearance.js','utf8').replace(/export /g,'')+'\n'+fs.readFileSync('static/js/material-expressions.js','utf8').replace(/^import .*;\r?\n/gm,'').replace(/export /g,'')+`\nwindow.key='model-a';window.edit={channel:'opacity',value:0};window.controller={colors:{part:{color:'#ff0000',strength:.7,opacity:1}},entry:id=>id==='part'?{name:'Jacket'}:null,setColor(id,v){this.colors[id]=v;}};window.presets=installMaterialExpressions({controller:()=>controller,key:()=>key,part:()=>'part',edit:()=>edit,save(){},changed(){}});presets.refresh();`});
 await page.locator('#material-expression-name').fill('Hide jacket');await page.locator('#save-material-expression').click();
 assert.equal(await page.evaluate(()=>controller.colors.part.opacity),0);assert.equal(await page.evaluate(()=>controller.colors.part.color),'#ff0000');
 await page.getByRole('switch').click();assert.equal(await page.evaluate(()=>controller.colors.part.opacity),1);
 await page.getByRole('switch').click();await page.evaluate(()=>edit={channel:'color',value:{color:'#00ff00',strength:1}});
 await page.locator('#material-expression-name').fill('Green jacket');await page.locator('#save-material-expression').click();assert.equal(await page.evaluate(()=>controller.colors.part.opacity),0);
 await page.getByRole('switch').nth(1).click();assert.equal(await page.evaluate(()=>controller.colors.part.color),'#ff0000');assert.equal(await page.evaluate(()=>controller.colors.part.opacity),0);
 await page.evaluate(()=>{key='model-b';presets.refresh();});assert.equal(await page.getByRole('switch').count(),0);
 await page.evaluate(()=>{key='model-a';presets.refresh();});assert.equal(await page.getByRole('switch').count(),2);await page.getByRole('switch').first().click();assert.equal(await page.evaluate(()=>controller.colors.part.opacity),1);
 console.log('PASS: saved part expressions independently toggle color/opacity, restore prior values and stay model-specific.');
 }finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
