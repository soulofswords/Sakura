const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{chromium}=require('playwright');
const root=process.cwd();function find(dir,predicate){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory()){const v=find(p,predicate);if(v)return v;}else if(predicate(p))return p;}}
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=d3d11']});try{const page=await browser.newPage({viewport:{width:720,height:800}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('http://greeting.test/**',async route=>{const pathname=decodeURIComponent(new URL(route.request().url()).pathname);if(pathname.startsWith('/api/'))return route.fulfill({contentType:'application/json',body:route.request().method()==='POST'?'{"saved":true}':'{"repairs":null}'});const f=path.resolve(root,'.'+pathname);if(!f.startsWith(root+path.sep)||!fs.existsSync(f)||!fs.statSync(f).isFile())return route.fulfill({status:404,body:''});const mime={'.html':'text/html','.js':'text/javascript','.json':'application/json','.png':'image/png','.css':'text/css','.wasm':'application/wasm'}[path.extname(f)]||'application/octet-stream';return route.fulfill({contentType:mime,body:fs.readFileSync(f)});});await page.goto('http://greeting.test/static/physics-check.html');await page.waitForFunction(()=>window.viewer?.physics);

await page.addStyleTag({content:'#tools{display:none}'});const reports=[];
const selected=[find('models/pmx/anime/kakeguri',p=>/TDA Ririka Momobami the Vice President\.pmx$/i.test(p)),find('models/vrm',p=>/\.vrm$/i.test(p))];
for(const [index,file] of selected.entries()){
 await page.evaluate(async url=>{await viewer.loadModel(url);viewer.fullModelView=true;viewer._autoFrame(viewer.model);await new Promise(r=>setTimeout(r,1100));},'/'+file.split(path.sep).map(encodeURIComponent).join('/'));
 const report=await page.evaluate(async()=>{
  const {default:LipSync}=await import('/static/js/lip-sync.js?v=session87');
  const lip=new LipSync(viewer);let started=false,maxLift=-Infinity,mouth=0;
  const getLift=()=>{viewer.model.updateMatrixWorld(true);const b=viewer.animationBones,pos=b=>b.getWorldPosition(b.position.clone());
   const shoulder=pos(b.rightArm.bone),elbow=pos(b.rightElbow.bone),hand=pos(b.rightWrist.bone);return (hand.y-shoulder.y)/(shoulder.distanceTo(elbow)+elbow.distanceTo(hand));};
  const initialLift=getLift(),timer=setInterval(()=>{if(started)maxLift=Math.max(maxLift,getLift());mouth=Math.max(mouth,...Object.values(lip.current));},16);
  // Use fixture audio to exercise real playback timing without mic or cloud.
  const promise=lip.playWithLipSync('/static/audio/reactions/laugh-belly.wav?v=natural86',()=>{if(!lip.isPlaying)throw Error('Gesture started before audio');started=viewer.dance.start('greeting_wave');});
  await new Promise(r=>setTimeout(r,900));window.greetingCheck={started};await promise;clearInterval(timer);
  return {started,initialLift,maxLift,mouth,finite:Object.values(viewer.animationBones).every(e=>e.bone.quaternion.toArray().every(Number.isFinite))};
 });
 assert.ok(report.started&&report.finite);assert.ok(report.maxLift>.35,JSON.stringify(report));assert.ok(report.mouth>.4);reports.push({file,...report});console.log(JSON.stringify(reports.at(-1)));
 await page.waitForFunction(()=>!viewer.dance.active);
 await page.evaluate(()=>viewer.dance.start('greeting_wave'));await page.waitForTimeout(950);await page.screenshot({path:'audit-results/ririka-fbx-before-'+index+'.png'});await page.waitForFunction(()=>!viewer.dance.active);
}
assert.deepEqual(errors,[]);fs.writeFileSync('audit-results/ririka-fbx-before.json',JSON.stringify({reports,errors},null,2));console.log('PASS: real PMX/VRM greeting hand raises above shoulder during audible playback, finite motion and automatic completion');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
