const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});try{
 let permission=false,deny=false;const permissions=[];
 const page=await browser.newPage();await page.route('http://appearance.test/**',route=>{
  if(route.request().method()==='POST'){
   const body=route.request().postDataJSON();if('computer_control_enabled' in body){permissions.push(body.computer_control_enabled);if(deny)return route.fulfill({status:500,json:{error:'Could not save permission.'}});permission=body.computer_control_enabled;}
   return route.fulfill({json:{ok:true}});
  }
  return route.fulfill({json:{ui_theme:'dark',computer_control_enabled:permission}});
 });
 await page.goto('http://appearance.test/');await page.setContent('<div id="tab-theme"></div><input id="computer-control-toggle" type="checkbox"><input id="system-tools-permission" type="checkbox">');
 await page.evaluate(()=>{window.SAKURA_EDITION='companion';window.startupChanges=[];window.pywebview={api:{windows_startup_status:async()=>({supported:true,enabled:false}),set_windows_startup:async enabled=>{window.startupChanges.push(enabled);return {supported:true,enabled};}}};});
 await page.addScriptTag({content:fs.readFileSync('static/js/appearance.js','utf8').replace('export function','function')});
 const toggle=page.getByRole('checkbox',{name:'Run Sakura when Windows starts'});await toggle.check();await toggle.uncheck();assert.deepEqual(await page.evaluate(()=>window.startupChanges),[true,false]);
 const access=page.getByRole('switch',{name:'Computer access'});await access.check();
 await page.waitForFunction(()=>document.getElementById('theme-computer-access').getAttribute('aria-checked')==='true');
 assert.equal(permission,true);assert.equal(await page.locator('#computer-control-toggle').isChecked(),true);
 await access.uncheck();await page.waitForFunction(()=>!document.getElementById('theme-computer-access').disabled);assert.equal(permission,false);
 assert.deepEqual(permissions,[true,false]);deny=true;await access.check();
 await page.waitForFunction(()=>!document.getElementById('theme-computer-access').disabled);
 assert.equal(await access.isChecked(),false,'A failed save cannot show permission as enabled');
 await page.setContent('<div id="tab-theme"></div>');await page.evaluate(()=>{window.SAKURA_EDITION='vtuber';window.installAppearance();});assert.equal(await page.locator('#windows-startup-setting').count(),0);assert.equal(await page.locator('#computer-access-setting').count(),0);
 console.log('PASS: Companion Theme startup checkbox enables/disables native startup and is absent from standalone VTuber.');
}finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
