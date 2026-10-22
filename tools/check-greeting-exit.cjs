const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{chromium}=require('playwright');
const root=process.cwd();function find(dir,predicate){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory()){const v=find(p,predicate);if(v)return v;}else if(predicate(p))return p;}}
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=d3d11']});try{const page=await browser.newPage({viewport:{width:720,height:800}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('http://greeting.test/**',async route=>{const pathname=decodeURIComponent(new URL(route.request().url()).pathname);if(pathname.startsWith('/api/'))return route.fulfill({contentType:'application/json',body:route.request().method()==='POST'?'{"saved":true}':'{"repairs":null}'});const f=path.resolve(root,'.'+pathname);if(!f.startsWith(root+path.sep)||!fs.existsSync(f)||!fs.statSync(f).isFile())return route.fulfill({status:404,body:''});const mime={'.html':'text/html','.js':'text/javascript','.json':'application/json','.png':'image/png','.css':'text/css','.wasm':'application/wasm'}[path.extname(f)]||'application/octet-stream';return route.fulfill({contentType:mime,body:fs.readFileSync(f)});});await page.goto('http://greeting.test/static/physics-check.html');await page.waitForFunction(()=>window.viewer?.physics);


await page.addStyleTag({content:'#tools{display:none}'});
const file=find('models/pmx/anime/kakeguri',p=>/TDA Ririka Momobami the Vice President\.pmx$/i.test(p));
await page.evaluate(async url=>{await viewer.loadModel(url);viewer.fullModelView=true;viewer._autoFrame(viewer.model);await viewer.dance.prepare('greeting_wave');await new Promise(r=>setTimeout(r,1200));viewer.dance.start('greeting_wave');},'/'+file.split(path.sep).map(encodeURIComponent).join('/'));
const reports=[];for(const target of [0.5,1.5,3,4.4,5,5.8,6.6]){
 await page.waitForFunction(t=>!viewer.dance.active||viewer.dance.active.time>=t,target);
 const sample=await page.evaluate(()=>{const b=viewer.animationBones,p=k=>b[k].bone.getWorldPosition(b[k].bone.position.clone());viewer.model.updateMatrixWorld(true);const shoulder=p('rightArm'),elbow=p('rightElbow'),hand=p('rightWrist');return {time:viewer.dance.active?.time||0,active:!!viewer.dance.active,lift:(hand.y-shoulder.y)/(shoulder.distanceTo(elbow)+elbow.distanceTo(hand))};});
 await page.screenshot({path:'audit-results/ririka-exit-after-'+target+'.png'});reports.push(sample);console.log(JSON.stringify(sample));if(sample.time>=4.4||!sample.active)assert.ok(sample.lift<-.9,'Greeting exit must stay relaxed, not spread toward import pose: '+JSON.stringify(sample));
}
fs.writeFileSync('audit-results/ririka-exit-after.json',JSON.stringify(reports,null,2));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
