const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{chromium}=require('playwright');
const root=process.cwd();function find(dir,predicate){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory()){const v=find(p,predicate);if(v)return v;}else if(predicate(p))return p;}}
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=d3d11']});try{const page=await browser.newPage({viewport:{width:720,height:800}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('http://speech.test/**',async route=>{const pathname=decodeURIComponent(new URL(route.request().url()).pathname);if(pathname.startsWith('/api/'))return route.fulfill({contentType:'application/json',body:route.request().method()==='POST'?'{"saved":true}':'{"repairs":null}'});const f=path.resolve(root,'.'+pathname);if(!f.startsWith(root+path.sep)||!fs.existsSync(f)||!fs.statSync(f).isFile())return route.fulfill({status:404,body:''});const mime={'.html':'text/html','.js':'text/javascript','.json':'application/json','.png':'image/png','.css':'text/css','.wasm':'application/wasm'}[path.extname(f)]||'application/octet-stream';return route.fulfill({contentType:mime,body:fs.readFileSync(f)});});await page.goto('http://speech.test/static/physics-check.html');await page.waitForFunction(()=>window.viewer?.physics);

const selected=[find('models',p=>/Ringo\.pmx$/i.test(p)),find('models/vrm',p=>/\.vrm$/i.test(p)),find('models/live2d',p=>/miu2022\.model3\.json$/i.test(p))];assert.ok(selected.every(Boolean));const reports=[];
for(const file of selected){
 const result=await page.evaluate(async url=>{
  await viewer.loadModel(url);await new Promise(r=>setTimeout(r,1100));
  const {default:LipSync}=await import('/static/js/lip-sync.js?v=speech82');
  const lip=new LipSync(viewer),original=viewer.setVowelWeights.bind(viewer);let peak=0;
  viewer.setVowelWeights=weights=>{peak=Math.max(peak,...Object.values(weights));original(weights);};
  await lip.playWithLipSync('/static/audio/reactions/laugh-short.wav');
  const stopped=!lip.isPlaying&&!viewer.audioPlaybackActive&&Object.values(lip.current).every(x=>x===0);
  let pose=null;
  if(!viewer.live2d){
   const dance=viewer.dance;dance.start('laugh_bend');
   for(let i=0;i<90;i++)dance.update(1/60);
   pose={bend:viewer.animationBones.torso.bone.rotation.x,finite:Object.values(viewer.animationBones).every(e=>e.bone.quaternion.toArray().every(Number.isFinite))};
  }else {
   viewer.audioPlaybackActive=true;viewer.setVowelWeights({A:.85,I:0,U:0,E:0,O:0});viewer.setActivity('talking');viewer.live2d.applyAudioMouth();
   const core=viewer.live2d.avatar.internalModel.coreModel;
   const index=core.getParameterIndex('ParamMouthOpenY');
   if(index>=0&&core.getParameterValueByIndex(index)<.8)throw Error('Live2D mouth parameter did not open');
   viewer.audioPlaybackActive=false;viewer.resetMouth();
  }
  return {url,peak,stopped,pose};
 },'/'+file.split(path.sep).map(encodeURIComponent).join('/'));
 assert.ok(result.peak>.45&&result.peak<=1,JSON.stringify(result));assert.ok(result.stopped,JSON.stringify(result));
 if(result.pose){assert.ok(result.pose.finite);await page.screenshot({path:'audit-results/speech-laugh-'+reports.length+'.png'});await page.evaluate(()=>viewer.dance.stop(true));}
 reports.push(result);console.log(JSON.stringify(result));
}
assert.deepEqual(errors,[]);fs.writeFileSync('audit-results/speech-gesture-runtime.json',JSON.stringify({reports,errors},null,2));console.log('PASS: real PMX/VRM/Live2D audio-driven mouth and silence cleanup; finite 3D laugh poses');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
