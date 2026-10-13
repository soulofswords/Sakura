const {chromium}=require('playwright');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=d3d11']});
 try {
  const page=await browser.newPage({viewport:{width:700,height:850}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8766/static/library-audit.html?no-capture');
  await page.waitForFunction(()=>window.auditReady);
  if(process.env.SAKURA_NO_PHYSICS) await page.evaluate(()=>window.auditViewer.setPhysicsMode('off'));
  const model=process.env.SAKURA_CHECK_MODEL || 'pmx/Miku universe/Miku/Miku-Elegant Princess/Miku-Elegant Princess.pmx';
  const result=await page.evaluate(model=>window.auditModel(model),model);
  if(process.env.SAKURA_HIDE_MATERIAL) await page.evaluate(name=>{window.auditViewer.model.traverse(n=>{for(const m of (Array.isArray(n.material)?n.material:[n.material]))if(m?.name===name)m.visible=false;});window.auditViewer._renderFrame();},process.env.SAKURA_HIDE_MATERIAL);
  await page.screenshot({path:'audit-results/cutout-recording/princess-current.png'});
  fs.writeFileSync('audit-results/cutout-recording/princess-render.json',JSON.stringify({result,errors},null,2));
  console.log(JSON.stringify({ok:result.ok,errors,notice:result.notice}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
