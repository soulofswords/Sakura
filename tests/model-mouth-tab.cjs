const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});try{
 const page=await browser.newPage({viewport:{width:480,height:960}});
 const html=fs.readFileSync('static/index.html','utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace(/<link[^>]*rel="stylesheet"[^>]*>/g,'');
 await page.setContent(html);await page.addStyleTag({content:fs.readFileSync('static/css/style.css','utf8')});
 await page.evaluate(()=>{
  window.viewer={camera:{zoom:1},vtuberTrackingMode:false};
  window.installColorDial=()=>({sync(){}});
  for(const key of ['installBoneSettings','installTextureDiagnostics','installMouthSettings','installLive2DFaceMapping','installPmxAppearance','installMaterialExpressions'])window[key]=()=>({refresh(){},stop(){}});
  document.getElementById('expression-modal').classList.remove('hidden');
 });
 await page.addScriptTag({content:fs.readFileSync('static/js/model-settings.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export function','function')+';window.settings=installModelSettings(()=>viewer,()=>"test",()=>{},()=>"",()=>{});'});
 for(const tracking of [false,true]){
  await page.evaluate(async value=>{viewer.vtuberTrackingMode=value;document.body.classList.toggle('tracking-only',value);await settings.refresh();},tracking);
  const tab=page.locator('[data-model-tab="mouth"]');assert.equal(await tab.isVisible(),true);
  await tab.click();assert.equal(await page.locator('[data-model-panel="mouth"]').isVisible(),true);
  assert.equal(await page.locator('[data-model-panel="coloring"]').isVisible(),false);
 }
 console.log('PASS: Mouth tab visible and opens its controls with tracking off or on, including narrow windows.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
