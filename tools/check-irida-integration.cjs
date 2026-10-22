const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{chromium}=require('playwright');
const root=process.cwd();function find(dir,predicate){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory()){const v=find(p,predicate);if(v)return v;}else if(predicate(p))return p;}}
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=d3d11']});try{const page=await browser.newPage({viewport:{width:720,height:800}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('http://speech.test/**',async route=>{const pathname=decodeURIComponent(new URL(route.request().url()).pathname);if(pathname.startsWith('/api/'))return route.fulfill({contentType:'application/json',body:route.request().method()==='POST'?'{"saved":true}':'{"repairs":null}'});const f=path.resolve(root,'.'+pathname);if(!f.startsWith(root+path.sep)||!fs.existsSync(f)||!fs.statSync(f).isFile())return route.fulfill({status:404,body:''});const mime={'.html':'text/html','.js':'text/javascript','.json':'application/json','.png':'image/png','.css':'text/css','.wasm':'application/wasm'}[path.extname(f)]||'application/octet-stream';return route.fulfill({contentType:mime,body:fs.readFileSync(f)});});await page.goto('http://speech.test/static/physics-check.html');await page.waitForFunction(()=>window.viewer?.physics);

const selected=['models/pmx/AI_Assistant_PMX_Models/Repair_2026_10_22/Irida_Repaired.pmx'];assert.ok(selected.every(Boolean));const reports=[];
for(const file of selected){
 const result=await page.evaluate(async url=>{
  await viewer.loadModel(url);await new Promise(r=>setTimeout(r,1100));
  console.log('IRIDA RIG',JSON.stringify(Object.fromEntries(Object.entries(viewer.animationBones).map(([k,e])=>[k,e.bone.name]))));
  if(!viewer.partVisibility?.has('Hide_Wings'))throw Error('Missing authored visibility controls');
  viewer.setEnvironmentColor('#ffffff',1);viewer.setDisplaySize(65);
  const visibility=await import('/static/js/model-visibility.js?v=irida101');
  const markup=new DOMParser().parseFromString(await(await fetch('/static/index.html')).text(),'text/html');
  document.body.append(document.importNode(markup.querySelector('#expression-modal'),true));
  for(const id of ['expression-editor-btn'])if(!document.getElementById(id)){const b=document.createElement('button');b.id=id;document.body.append(b);}
  const {installExpressionEditor}=await import('/static/js/expression-editor.js?v=irida101');
  for(const morph of ['Hide_Wings','Hide_Horns','Hide_Top'])visibility.setPartVisible(viewer,morph,true);
  viewer.areAiExpressionsAutomatic=()=>true;
  const editor=installExpressionEditor(()=>viewer,()=>url);editor.refresh();
  for(const [morph,name]of [['Hide_Wings','Irida_Wings'],['Hide_Horns','Irida_Horns'],['Hide_Top','Irida_Top']]){
   const card=[...document.querySelectorAll('.expression-card')].find(c=>c.dataset.expression===morph);
   if(!card)throw Error('Missing UI card '+morph);
   const buttons=card.querySelectorAll('button');if(buttons[0].disabled)throw Error('Visibility disabled with reactions on');
   viewer.scene.updateMatrixWorld(true);viewer.camera.updateMatrixWorld(true);
   const captured=viewer.captureSpoutFrame(640);const before={pixels:new Uint8Array(captured.pixels)};
   buttons[0].click();await new Promise(r=>setTimeout(r,200));viewer._renderFrame();
   const after=viewer.captureSpoutFrame(640);let changedPixels=0;for(let i=0;i<before.pixels.length;i+=4)if(Math.abs(before.pixels[i]-after.pixels[i])+Math.abs(before.pixels[i+1]-after.pixels[i+1])+Math.abs(before.pixels[i+2]-after.pixels[i+2])+Math.abs(before.pixels[i+3]-after.pixels[i+3])>30)changedPixels++;
   if(changedPixels<25)throw Error('No rendered change '+morph);window.visibilityPixelReport||=[];window.visibilityPixelReport.push({morph,changedPixels,beforeAlpha:before.pixels.filter((v,i)=>i%4===3&&v>0).length,afterAlpha:after.pixels.filter((v,i)=>i%4===3&&v>0).length});
   let target;viewer.model.traverse(n=>{for(const material of Array.isArray(n.material)?n.material:n.material?[n.material]:[])if(material.name===name)target=material;});
   if(target?.visible!==false)throw Error('Expression Preview did not hide '+name);
   buttons[3].click();viewer._renderFrame();if(target.visible!==true)throw Error('Expression Off did not show '+name);
  }
  viewer.areAiExpressionsAutomatic=()=>false;

  const materialState=()=>{const state={};viewer.model.traverse(n=>{for(const m of Array.isArray(n.material)?n.material:n.material?[n.material]:[])state[m.name]=m.visible;});return state;};
  const visibleBaseline=materialState();
  for(const [morph,names]of [['Hide_Wings',['Irida_Wings']],['Hide_Horns',['Irida_Horns']],['Hide_Top',['Irida_Top']]]){
   visibility.setPartVisible(viewer,morph,false);viewer._renderFrame();const state=materialState();
   for(const name of names)if(state[name]!==false)throw Error('Visibility did not hide '+name);
   if(state.wing!==visibleBaseline.wing||state.skin!==visibleBaseline.skin)throw Error('Visibility affected tail or skin');
   visibility.setPartVisible(viewer,morph,true);viewer._renderFrame();
   for(const name of names)if(materialState()[name]!==visibleBaseline[name])throw Error('Restore failed '+name);
  }
  viewer.setActivity('idle');
  for(let i=0;i<180;i++)viewer._animateCharacter(1/60,i/60);
  viewer.model.updateMatrixWorld(true);
  const THREE=await import('three');
  const armDirections={};
  for(const side of ['left','right']){
   const a=viewer.animationBones[side+'Arm'].bone.getWorldPosition(new THREE.Vector3());
   const b=viewer.animationBones[side+'Elbow'].bone.getWorldPosition(new THREE.Vector3());
   const d=b.sub(a).normalize();armDirections[side]=d.toArray();if(d.y>-.90)throw Error('Arm still in A pose '+side+': '+d.y);
  }
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
  viewer.dance.stop(true);viewer.setActivity('talking');for(let i=0;i<120;i++)viewer._animateCharacter(1/60,2+i/60);
  return {url,peak,stopped,pose,armDirections,groups:viewer.model.geometry.groups,materials:viewer.model.material.map(m=>({name:m.name,visible:m.visible})),visibilityPixels:window.visibilityPixelReport,rig:Object.fromEntries(Object.entries(viewer.animationBones).map(([k,e])=>[k,{name:e.bone.name,rotation:e.bone.rotation.toArray()}]))};
 },'/'+file.split(path.sep).map(encodeURIComponent).join('/'));
 assert.ok(result.peak>.45&&result.peak<=1,JSON.stringify(result));assert.ok(result.stopped,JSON.stringify(result));
 if(result.pose){assert.ok(result.pose.finite);await page.screenshot({path:'audit-results/speech-laugh-'+reports.length+'.png'});await page.evaluate(()=>viewer.dance.stop(true));}
 reports.push(result);console.log(JSON.stringify(result));
}
assert.deepEqual(errors,[]);fs.writeFileSync('audit-results/irida-integration-runtime.json',JSON.stringify({reports,errors},null,2));console.log('PASS: Irida mouth/audio reset, finite arm gestures and explicit independent material visibility');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
