// Render owner-approved PMX/VRM previews through Sakura's existing renderer.
// Usage: node tools/render-library-turntable.cjs <models-relative-path> <output.webp> [http://127.0.0.1:8766]
const {chromium}=require('playwright');
const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path');
const {spawnSync}=require('node:child_process');
(async()=>{
 const [model,output,server='http://127.0.0.1:8766']=process.argv.slice(2);
 if(!model||!output||! /\.(pmx|vrm)$/i.test(model))throw Error('Choose a PMX or VRM model and output WebP path.');
 const url=new URL(server);
 if(!['127.0.0.1','localhost'].includes(url.hostname)||url.protocol!=='http:')throw Error('Use the local owner preview server.');
 const temporary=await fs.mkdtemp(path.join(os.tmpdir(),'sakura-turntable-'));
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage({viewport:{width:384,height:384},deviceScaleFactor:1});
  await page.goto(server+'/static/library-audit.html?no-capture');
  await page.waitForFunction(()=>window.auditReady);
  const loaded=await page.evaluate(async model=>{
   const v=window.auditViewer;
   cancelAnimationFrame(v.animationFrame);v.animate=()=>{};
   await v.loadModel('/models/'+model.split('/').map(encodeURIComponent).join('/'));
   return !!v.model;
  },model);
  if(!loaded)throw Error('The character did not render successfully.');
  await page.evaluate(()=>{
   const v=window.auditViewer;
   v.vrm?.humanoid?.resetNormalizedPose?.();v.vrm?.springBoneManager?.reset?.();
   if(!v.vrm)v.model.skeleton?.pose?.();
   v.model.updateMatrixWorld(true);v.desktopMode=true;v._autoFrame(v.model);
   v.controls.enabled=false;v._libraryTurntableStart=v.model.rotation.y;
  });
  for(let i=0;i<48;i++){
   await page.evaluate(angle=>{
    const v=window.auditViewer;v.model.rotation.y=v._libraryTurntableStart+angle;
    v.model.updateMatrixWorld(true);v.renderer.render(v.scene,v.camera);
   },i*Math.PI*2/48);
   await page.screenshot({path:path.join(temporary,`frame-${String(i).padStart(3,'0')}.png`)});
  }
  const root=path.resolve(__dirname,'..');
  const result=spawnSync(path.join(root,'venv/Scripts/python.exe'),['-c',
   'import sys; from model_library_previews import turntable_frames; turntable_frames(sys.argv[1],sys.argv[2])',temporary,path.resolve(output)],{cwd:root,encoding:'utf8'});
  if(result.status!==0)throw Error(result.stderr||'Could not encode preview.');
  console.log('Created rotating 3D preview:',path.resolve(output));
 }finally{
  await browser.close();
  const resolved=path.resolve(temporary),parent=path.resolve(os.tmpdir());
  if(path.dirname(resolved)!==parent||!path.basename(resolved).startsWith('sakura-turntable-'))throw Error('Unexpected temporary frame directory.');
  await fs.rm(resolved,{recursive:true,force:true});
 }
})().catch(error=>{console.error(error.message);process.exitCode=1;});
