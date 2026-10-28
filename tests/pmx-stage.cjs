const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});try{
 const page=await browser.newPage();await page.route('http://127.0.0.1:9988/**',r=>r.fulfill({json:{models:[{name:'Garden',path:'pmx/props/garden.pmx'}]}}));await page.goto('http://127.0.0.1:9988/');
 await page.evaluate(()=>{document.body.innerHTML='<div data-studio-content="background"></div>';document.body.className='tracking-only';window.loads=[];window.removed=[];window.viewer={model:{name:'Character'},scene:{add:m=>{window.added=m;}}};window.THREE={LoadingManager:class{addHandler(){}setURLModifier(){}}};window.TGALoader=window.DDSLoader=class{};window.MMDLoader=class{async loadAsync(url){loads.push(url);return {position:{set(...v){this.values=v;}},scale:{setScalar(v){this.value=v;}},rotation:{},updateMatrixWorld(){},removeFromParent(){removed.push(this);},traverse(){}};}};});
 await page.addScriptTag({content:fs.readFileSync('static/js/pmx-stage.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export class','class').replace(/export function/g,'function')+';window.stage=new PmxStage(viewer);'});
 assert(await page.evaluate(()=>{const geometry={morphAttributes:{position:[],normal:[1]}};prepareStageMesh({traverse(fn){fn({geometry});}});return !('position' in geometry.morphAttributes)&&geometry.morphAttributes.normal.length===1;}),'Static accessories drop empty morph arrays before shader compilation');
 assert(await page.evaluate(()=>{
  const origin=location.origin,path='pmx/import-demo/stage/garden.pmx';
  if(!stageAssetUrl('/models/pmx/import-demo/textures/stone.png',path).startsWith(origin))return false;
  for(const url of ['https://example.com/texture.png','/models/pmx/other/private.png','/models/pmx/import-demo/../../other/private.png','/models/pmx/import-demo/%2e%2e%2fother.png']){try{stageAssetUrl(url,path);return false;}catch{}}
  return true;
 }),'Texture requests stay inside the imported package, including shared textures and encoded traversal');
 assert.equal(await page.locator('#pmx-stage-options').isVisible(),false);assert.equal(await page.evaluate(()=>loads.length),0);
 await page.locator('#pmx-stage-enabled').check();await page.locator('#pmx-stage-library').selectOption('pmx/props/garden.pmx');await page.locator('#pmx-stage-add').click();await page.waitForFunction(()=>loads.length===1&&window.added);
 assert.equal(await page.evaluate(()=>viewer.model.name),'Character');
 await page.locator('#pmx-stage-x').fill('7');await page.locator('#pmx-stage-x').dispatchEvent('change');assert.equal(await page.evaluate(()=>added.position.values[0]),7);
 await page.locator('#pmx-stage-enabled').uncheck();assert.equal(await page.evaluate(()=>removed.length),1);assert.equal(await page.evaluate(()=>stage.records.length),1);
 await page.locator('#pmx-stage-enabled').check();await page.waitForFunction(()=>loads.length===2);await page.locator('#pmx-stage-remove').click();assert.equal(await page.evaluate(()=>stage.records.length),0);
 console.log('PASS: PMX scenery opt-in, independent character, transforms, unload/reload and removal.');
 }finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
