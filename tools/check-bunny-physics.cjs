const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{const root=path.resolve(__dirname,'..');const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=d3d11']});try{
 const page=await browser.newPage({viewport:{width:800,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('http://taffy.test/**',async route=>{const u=new URL(route.request().url());if(u.pathname.startsWith('/api/'))return route.fulfill({contentType:'application/json',body:route.request().method()==='POST'?'{"saved":true}':'{"repairs":null}'});const f=path.resolve(root,'.'+decodeURIComponent(u.pathname));if(!f.startsWith(root+path.sep)||!fs.existsSync(f)||!fs.statSync(f).isFile())return route.fulfill({status:404,body:''});const mime={'.html':'text/html','.js':'application/javascript','.json':'application/json','.png':'image/png'}[path.extname(f)]||'application/octet-stream';await route.fulfill({contentType:mime,body:fs.readFileSync(f)});});
 await page.goto('http://taffy.test/static/physics-check.html');await page.waitForFunction(()=>window.viewer?.physics);const reports=[];

 const scan=dir=>fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?scan(path.join(dir,e.name)):[path.join(dir,e.name)]);
 const files=scan('models/pmx/Bunny').filter(f=>f.endsWith('.pmx')).map(f=>f.split(path.sep).join('/'));
 for(const file of files){const result=await page.evaluate(async file=>{
  await viewer.loadModel('/'+file.split('/').map(encodeURIComponent).join('/'));
  viewer.rigMonitor.capture=()=>{};viewer.rigMonitor.persist=()=>{};
  const p=viewer.physics,peaks=new Map(),monitor=viewer.rigMonitor;monitor.start(file);const initial=performance.now();
  for(let i=0;i<720;i++){p.update(1/60);monitor.sample(initial+i*1000/60);for(const n of p.nodes){const angle=n.bone.quaternion.angleTo(n.restQuat)*180/Math.PI;peaks.set(n.index,Math.max(peaks.get(n.index)||0,angle));}}
  const rig=p._rigContext?.mmdBones;
  if(rig?.some(b=>b.rigidBodyType===1||b.rigidBodyType===2))for(const n of p.nodes.filter(n=>n.category==='breast')){
   if(![1,2].includes(rig[n.index]?.rigidBodyType))throw Error('Chest adjustment bone added despite authored dynamics: '+n.bone.name);
  }
  const clothing=p.nodes.filter(n=>n.category==='cloth');
  let frozenCheck=null;
  if(clothing.length){
   const n=clothing.find(n=>n.bone.name==='RightClothArmR2')||clothing[0],entry=viewer.boneControls.entries.find(e=>e.bone===n.bone);
   viewer.boneControls.toggle(entry.id,true);
   for(let i=0;i<180;i++){p.update(1/60);viewer.boneControls.apply();}
   frozenCheck={name:n.bone.name,angle:n.bone.quaternion.angleTo(n.restQuat),particleDrift:n.pos.distanceTo(n.prev)};
   if(frozenCheck.angle>1e-6||frozenCheck.particleDrift>1e-6)throw Error('Frozen clothing was still simulated');
   const url='/'+file.split('/').map(encodeURIComponent).join('/');
   await viewer.loadModel(url);
   const restored=viewer.boneControls.entries.find(e=>e.name===n.bone.name);
   if(!viewer.boneControls.disabled.has(restored.id))throw Error('Clothing freeze lost on reload');
   frozenCheck.reloadRestored=true;
  }
  return {file,info:p.info,report:viewer.rigAnalysis,frozenCheck,largest:p.nodes.map(n=>({index:n.index,name:n.bone.name,category:n.category,peak:peaks.get(n.index)})).sort((a,b)=>b.peak-a.peak)};
 },file);reports.push(result);console.log(result.file+' checked');}
 fs.writeFileSync('audit-results/bunny-runtime-after.json',JSON.stringify({reports,errors},null,2));
 assert.deepEqual(errors,[]);
 for(const r of reports)for(const bone of r.largest.filter(n=>n.category==='cloth'))assert.ok(bone.peak<=18.001,JSON.stringify(bone));
 console.log('PASS: both Bunny PMX rigs loaded; clothing stays within 18 degrees, selective clothing freeze stops solver motion and survives reload; no browser errors');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
