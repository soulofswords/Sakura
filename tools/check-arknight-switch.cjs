const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{chromium}=require('playwright');
const root=process.cwd();function find(dir,predicate){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory()){const v=find(p,predicate);if(v)return v;}else if(predicate(p))return p;}}
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=d3d11']});try{const page=await browser.newPage({viewport:{width:720,height:800}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('http://arknight.test/**',async route=>{const pathname=decodeURIComponent(new URL(route.request().url()).pathname);if(pathname.startsWith('/api/'))return route.fulfill({contentType:'application/json',body:route.request().method()==='POST'?'{"saved":true}':'{"repairs":null}'});const f=path.resolve(root,'.'+pathname);if(!f.startsWith(root+path.sep)||!fs.existsSync(f)||!fs.statSync(f).isFile())return route.fulfill({status:404,body:''});const mime={'.html':'text/html','.js':'text/javascript','.json':'application/json','.png':'image/png','.css':'text/css','.wasm':'application/wasm'}[path.extname(f)]||'application/octet-stream';return route.fulfill({contentType:mime,body:fs.readFileSync(f)});});await page.goto('http://arknight.test/static/physics-check.html');await page.waitForFunction(()=>window.viewer?.physics);

const warnings=[];page.on('console',m=>{if((m.type()==='error'&&!/server responded with a status of 404/.test(m.text()))||/context lost|out of memory|GL_INVALID/i.test(m.text()))warnings.push(m.text());});
await page.addStyleTag({content:'#tools{display:none}'});
const files=[find('models/pmx/Ananta',p=>/Taffy\.pmx$/i.test(p)),...['Arclight','Ardelia','Rossi'].map(name=>find('models/pmx/arknights endfield',p=>path.basename(p)===name+'.pmx'))];
const reports=[];
for(const file of [files[0],files[1],files[0],files[2],files[0],files[3]]){
 const result=await page.evaluate(async url=>{
  let lost=0;const canvas=viewer.renderer.domElement,onLost=()=>lost++;canvas.addEventListener('webglcontextlost',onLost);
  const started=performance.now();await viewer.loadModel(url);
  const gl=viewer.renderer.getContext(),glError=gl.getError();
  const report={url,ms:performance.now()-started,glError,lost,loading:viewer._displayLoading,overlay:!!viewer.blockTransition.canvas,memory:{...viewer.renderer.info.memory},programs:viewer.renderer.info.programs.length};
  canvas.removeEventListener('webglcontextlost',onLost);return report;
 },'/'+file.split(path.sep).map(encodeURIComponent).join('/'));
 await page.screenshot({path:'audit-results/arknight-switch-'+reports.length+'.png'});await page.waitForFunction(()=>!viewer.blockTransition.canvas);reports.push(result);console.log(JSON.stringify(result));
}
fs.writeFileSync('audit-results/arknight-switch-after.json',JSON.stringify({reports,warnings,errors},null,2));assert.deepEqual(errors,[]);assert.deepEqual(warnings,[]);for(const r of reports)assert.equal(r.glError,0);
console.log('PASS: Ananta/Arknights sequential switches have no browser or WebGL errors');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
