const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{chromium}=require('playwright');
const root=process.cwd();function find(dir,predicate){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory()){const v=find(p,predicate);if(v)return v;}else if(predicate(p))return p;}}
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=d3d11']});try{const page=await browser.newPage({viewport:{width:720,height:800}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('http://laugh.test/**',async route=>{const pathname=decodeURIComponent(new URL(route.request().url()).pathname);if(pathname.startsWith('/api/'))return route.fulfill({contentType:'application/json',body:route.request().method()==='POST'?'{"saved":true}':'{"repairs":null}'});const f=path.resolve(root,'.'+pathname);if(!f.startsWith(root+path.sep)||!fs.existsSync(f)||!fs.statSync(f).isFile())return route.fulfill({status:404,body:''});const mime={'.html':'text/html','.js':'text/javascript','.json':'application/json','.png':'image/png','.css':'text/css','.wasm':'application/wasm'}[path.extname(f)]||'application/octet-stream';return route.fulfill({contentType:mime,body:fs.readFileSync(f)});});await page.goto('http://laugh.test/static/physics-check.html');await page.waitForFunction(()=>window.viewer?.physics);

const reports=[];const selected=[find('models',p=>/Ringo\.pmx$/i.test(p)),find('models/vrm',p=>/\.vrm$/i.test(p)),find('models/live2d',p=>/miu2022\.model3\.json$/i.test(p))];
for(const file of selected){
 await page.evaluate(async url=>{await viewer.loadModel(url);await new Promise(r=>setTimeout(r,1100));},'/'+file.split(path.sep).map(encodeURIComponent).join('/'));
 for(const style of ['laugh','laugh_bend']){
  const report=await page.evaluate(async style=>{
   const {default:LipSync}=await import('/static/js/lip-sync.js?v=laugh84'),{playGameLaughter}=await import('/static/js/game-laughter.js?v=laugh84');
   const lip=new LipSync(viewer),original=viewer.setVowelWeights.bind(viewer);let peak=0,seen=false;
   viewer.setVowelWeights=w=>{peak=Math.max(peak,...Object.values(w));seen ||=viewer.dance.active?.style===style;original(w);};
   const played=await playGameLaughter(style,viewer,lip,()=>true);
   viewer.setVowelWeights=original;
   return {style,played,peak,seen,playing:lip.isPlaying,live2d:!!viewer.live2d};
  },style);
  if(report.live2d){assert.equal(report.played,false);assert.equal(report.seen,false);assert.equal(report.peak,0);}
  else {assert.equal(report.played,true);assert.ok(report.seen);assert.ok(report.peak>.45&&report.peak<=1);assert.equal(report.playing,false);await page.waitForFunction(()=>!viewer.dance.active);}
  reports.push({file,...report});console.log(JSON.stringify(reports.at(-1)));
 }
}
assert.deepEqual(errors,[]);fs.writeFileSync('audit-results/direct-laugh-runtime.json',JSON.stringify({reports,errors},null,2));console.log('PASS: real PMX/VRM short/deep laugh audio and synchronized motion, automatic finish; Live2D excluded');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
