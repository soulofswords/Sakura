const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{chromium}=require('playwright');
const root=process.cwd();function find(dir,predicate){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory()){const v=find(p,predicate);if(v)return v;}else if(predicate(p))return p;}}
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=d3d11']});try{const page=await browser.newPage({viewport:{width:720,height:800}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('http://gesture.test/**',async route=>{const pathname=decodeURIComponent(new URL(route.request().url()).pathname);if(pathname.startsWith('/api/'))return route.fulfill({contentType:'application/json',body:route.request().method()==='POST'?'{"saved":true}':'{"repairs":null}'});const f=path.resolve(root,'.'+pathname);if(!f.startsWith(root+path.sep)||!fs.existsSync(f)||!fs.statSync(f).isFile())return route.fulfill({status:404,body:''});const mime={'.html':'text/html','.js':'text/javascript','.json':'application/json','.png':'image/png','.css':'text/css','.wasm':'application/wasm'}[path.extname(f)]||'application/octet-stream';return route.fulfill({contentType:mime,body:fs.readFileSync(f)});});await page.goto('http://gesture.test/static/physics-check.html');await page.waitForFunction(()=>window.viewer?.physics);

await page.addStyleTag({content:'#tools{display:none}'});const reports=[];
const selected=[find('models',p=>/Ringo\.pmx$/i.test(p)),find('models/vrm',p=>/\.vrm$/i.test(p))];
for(const [index,file] of selected.entries()){
 await page.evaluate(async url=>{await viewer.loadModel(url);viewer.fullModelView=true;viewer._autoFrame(viewer.model);await new Promise(r=>setTimeout(r,1100));if(!viewer.dance.start('chest_tap'))throw Error('Chest tap not supported');},'/'+file.split(path.sep).map(encodeURIComponent).join('/'));
 await page.waitForTimeout(1100);
 const report=await page.evaluate(()=>{
  const bones=viewer.animationBones,pos=b=>b.getWorldPosition(b.position.clone());viewer.model.updateMatrixWorld(true);
  const shoulder=pos(bones.rightArm.bone),elbow=pos(bones.rightElbow.bone),wrist=pos(bones.rightWrist.bone),chest=pos(bones.chest.bone);
  const length=shoulder.distanceTo(elbow)+elbow.distanceTo(wrist);
  return {distance:wrist.distanceTo(chest)/length,active:viewer.dance.active?.style,finite:Object.values(bones).every(e=>e.bone.quaternion.toArray().every(Number.isFinite))};
 });
 assert.ok(report.finite);assert.equal(report.active,'chest_tap');assert.ok(report.distance<.45,JSON.stringify(report));
 await page.screenshot({path:'audit-results/chest-tap-'+index+'.png'});reports.push({file,...report});console.log(JSON.stringify(reports.at(-1)));
 await page.waitForFunction(()=>!viewer.dance.active);await page.evaluate(()=>{viewer.dance.start('chest_tap');viewer.userTracking=true;viewer.dance.update(1/60);if(viewer.dance.active)throw Error('Tracking did not cancel gesture');viewer.userTracking=false;});
}
assert.deepEqual(errors,[]);fs.writeFileSync('audit-results/chest-tap-runtime.json',JSON.stringify({reports,errors},null,2));console.log('PASS: real PMX/VRM hand reaches chest, returns to normal, tracking cancels gesture, no browser errors');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
