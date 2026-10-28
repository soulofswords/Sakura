// Owner-only rotating previews through the actual Sakura renderer.
const {chromium}=require('playwright');
const fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {spawnSync}=require('node:child_process');
(async()=>{
 const directory=path.resolve(process.argv[2]||'../private-model-library-pmx');
 const checkpoint=path.join(directory,'prepared-models.json');
 const models=JSON.parse(await fs.readFile(checkpoint,'utf8'));
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 let done=0;const failures=[];
 const groups=new Map();
 for(const pair of Object.entries(models).filter(([,entry])=>!entry.preview)){
  const category=pair[1].name.split(' / ')[0];if(!groups.has(category))groups.set(category,[]);groups.get(category).push(pair);
 }
 const ordered=Object.entries(models).filter(([,entry])=>entry.preview);
 while([...groups.values()].some(group=>group.length))for(const group of groups.values())if(group.length)ordered.push(group.shift());
 const streamPublish=process.argv.includes('--stream-publish');let sincePublish=0;
 function publishReady(){
  if(!streamPublish)return;
  for(const args of [ ['tools/upload-library-jio.py','--directory',directory,'--remote-folder','PMX/Sakura library packages','--workers','2','--ready-only'], ['tools/publish-library-jio.py','--directory',directory,'--configure'] ]){
   const result=spawnSync('venv/Scripts/python.exe',args,{encoding:'utf8',timeout:600000});
   if(result.stdout)process.stdout.write(result.stdout);
   if(result.status!==0){console.log('Ready batch publication deferred; remaining previews will continue.');return;}
  }
 }

 try{
  for(const [id,entry]of ordered){
   const output=path.join(directory,id+'.webp');
   if(entry.preview){done++;continue;}
   const temporary=await fs.mkdtemp(path.join(os.tmpdir(),'sakura-cloud-preview-'));
   let page;
   try{
    page=await browser.newPage({viewport:{width:256,height:256},deviceScaleFactor:1});
    await page.goto('http://127.0.0.1:8796/static/library-audit.html?no-capture');
    await page.waitForFunction(()=>window.auditReady,{polling:100,timeout:60000});
    const loaded=await page.evaluate(async model=>{
     const v=window.auditViewer;cancelAnimationFrame(v.animationFrame);v.animate=()=>{};
     await v.loadModel('/models/'+model.split('/').map(encodeURIComponent).join('/'));
     if(!v.model)return false;
     v.model.skeleton?.pose?.();v.model.updateMatrixWorld(true);v.desktopMode=true;v._autoFrame(v.model);
     v.controls.enabled=false;v._previewStart=v.model.rotation.y;return true;
    },entry.preview_model);
    if(!loaded)throw Error('Model did not render');
    for(let i=0;i<16;i++){
     await page.evaluate(angle=>{const v=window.auditViewer;v.model.rotation.y=v._previewStart+angle;v.model.updateMatrixWorld(true);v.renderer.render(v.scene,v.camera);},i*Math.PI*2/16);
     await page.screenshot({path:path.join(temporary,`frame-${String(i).padStart(3,'0')}.png`)});
    }
    const encode=spawnSync('venv/Scripts/python.exe',['-c','import sys;from model_library_previews import turntable_frames;turntable_frames(sys.argv[1],sys.argv[2])',temporary,output],{encoding:'utf8'});
    if(encode.status!==0)throw Error('Preview encoding failed');
    entry.preview=true;const draft=checkpoint+'.preview-tmp';await fs.writeFile(draft,JSON.stringify(models,null,2));await fs.rename(draft,checkpoint);
    done++;sincePublish++;console.log('Rotating previews: '+done+'/'+Object.keys(models).length);
    if(sincePublish>=6){publishReady();sincePublish=0;}
   }catch(e){failures.push(id);console.log('Preview deferred: '+id+' · '+String(e.message).slice(0,180));}
   finally{
    await page?.close();
    if(path.dirname(temporary)!==path.resolve(os.tmpdir())||!path.basename(temporary).startsWith('sakura-cloud-preview-'))throw Error('Unexpected preview temp folder');
    await fs.rm(temporary,{recursive:true,force:true});
   }
  }
  if(sincePublish)publishReady();
  await fs.writeFile(path.join(directory,'preview-report.json'),JSON.stringify({done,failures},null,2));
  const privateFields=new Set(['source_folder','preview_model','source_fingerprint','models','excluded_non_avatar_models','variant_model']);
  const catalogue={version:1,models:Object.values(models).map(entry=>Object.fromEntries(Object.entries(entry).filter(([key])=>!privateFields.has(key))))};
  await fs.writeFile(path.join(directory,'catalogue.json'),JSON.stringify(catalogue,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
