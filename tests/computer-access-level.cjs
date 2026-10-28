const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});try{
 const page=await browser.newPage();let cfg={ui_theme:'dark',computer_control_enabled:true,computer_access_level:'restricted'};const writes=[];
 await page.route('http://access.test/**',route=>{
  if(new URL(route.request().url()).pathname==='/api/settings'){
   if(route.request().method()==='POST'){const data=route.request().postDataJSON();writes.push(data);Object.assign(cfg,data);return route.fulfill({json:{ok:true}});}
   return route.fulfill({json:cfg});
  }
  if(new URL(route.request().url()).pathname==='/api/version')return route.fulfill({json:{version:'1.0.1',product:'Sakura Companion'}});
  return route.fulfill({contentType:'text/html',body:'<div id="tab-theme"></div>'});
 });
 await page.goto('http://access.test/');await page.addScriptTag({content:fs.readFileSync('static/js/appearance.js','utf8').replace('export function','function')});
 const level=page.locator('#computer-access-level');await page.waitForFunction(()=>!document.getElementById('computer-access-level').disabled);
 assert.equal(await level.inputValue(),'restricted');await level.selectOption('full');await page.waitForFunction(()=>!document.getElementById('computer-access-level').disabled);
 assert(writes.some(data=>data.computer_access_level==='full'));
 await page.locator('#theme-computer-access').uncheck();await page.waitForFunction(()=>!document.getElementById('theme-computer-access').disabled);
 assert(await level.isDisabled());assert.equal(cfg.computer_control_enabled,false);
 console.log('PASS: Restricted/Full computer access is loaded, saved and disabled when access is off.');
}finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1});
