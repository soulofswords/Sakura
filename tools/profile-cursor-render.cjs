// Read-only local rendering benchmark. No camera, microphone, or AI requests.
const {chromium}=require('playwright');
const fs=require('node:fs/promises'),path=require('node:path');
(async()=>{
 const base='http://127.0.0.1:8798';
 const modelRoot='F:/AI/assistant/Sakura VTuber/Sakura/models';
 const selected=process.argv[2]||'vrm/1439626354518702295.vrm';
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=d3d11']});
 try{
 const page=await browser.newPage({viewport:{width:1920,height:1080}});
 page.on('pageerror',e=>console.error('page:',e.message));
 await page.route('**/*',async r=>{
  const url=new URL(r.request().url()),name=decodeURIComponent(url.pathname);
  if(name==='/__cursor_profile')return r.fulfill({contentType:'text/html',body:`<!doctype html><title>Sakura VTuber profile</title><style>body{margin:0}#stage{width:100vw;height:100vh}</style><script type="importmap">{"imports":{"three":"/static/vendor/three/build/three.module.js","three/addons/":"/static/vendor/three/examples/jsm/"}}</script><div id="stage"></div>`});
  if(name==='/api/models')return r.fulfill({json:{models:[{path:selected}]}});
  if(name.startsWith('/api/'))return r.fulfill({json:{ok:true,missing:[],optional_missing:[]}});
  const root=name.startsWith('/static/')?path.resolve('static'):name.startsWith('/models/')?path.resolve(modelRoot):null;
  if(!root)return r.abort();
  const file=path.resolve(root,name.replace(/^\/(static|models)\//,''));
  if(!file.startsWith(root+path.sep))return r.abort();
  try{
   const body=await fs.readFile(file),ext=path.extname(file);
   return r.fulfill({body,contentType:{'.js':'application/javascript','.mjs':'application/javascript','.wasm':'application/wasm','.json':'application/json','.png':'image/png','.jpg':'image/jpeg','.css':'text/css'}[ext]||'application/octet-stream'});
  }catch(e){console.error('missing:',name);return r.fulfill({status:404,body:'Missing local asset'});}
 });
 await page.goto(base+'/__cursor_profile');
 console.log(await page.evaluate(async()=>{
  const {default:Viewer}=await import('/static/js/model-viewer.js?v=cursor-rig5');
  const models=await (await fetch('/api/models')).json();
  const model=models.models[0];
  window.viewer=new Viewer('stage');
  await viewer.loadModel('/models/'+model.path);
  viewer.vtuberTrackingMode=true;viewer.eyeTrackingEnabled=true;
  const gl=viewer.renderer.getContext(),ext=gl.getExtension('WEBGL_debug_renderer_info');
  return {model:model.path,gpu:ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),size:viewer.renderer.domElement.width+'x'+viewer.renderer.domElement.height};
 }));
 await page.waitForTimeout(5000);
 console.log(await page.evaluate(()=>{
  const v=window.viewer;
  return {picking:[[960,500],[15,15],[960,250]].map(([x,y])=>({x,y,gpu:v._hitModelPixelAt(x,y),cpu:v._hitModelAt(x,y)}))};
 }));
 for(const hover of [false,true]){
 const result=await page.evaluate(async hover=>{
  const v=window.viewer,stats={};
  const wrap=(object,key,name)=>{const original=object?.[key];if(typeof original!=='function')return;object[key]=function(...args){const start=performance.now();try{return original.apply(this,args);}finally{const sample=stats[name]||={count:0,total:0,max:0};const cost=performance.now()-start;sample.count++;sample.total+=cost;sample.max=Math.max(sample.max,cost);}};};
  wrap(v,'_renderFrame','frame');wrap(v,'_animateCharacter','character');wrap(v,'_animateEyeTracking','gaze');wrap(v.vrm,'update','vrm');wrap(v.physics,'update','physics');wrap(v,'_updateModelDragCursor','hover');wrap(v.renderer,'render','gpuSubmit');
  const times=[];const started=performance.now();
  await new Promise(resolve=>{const step=()=>{const now=performance.now();times.push(now);v.setEyeTrackingTarget(Math.sin(now/200),Math.cos(now/500));if(hover)v.renderer.domElement.dispatchEvent(new PointerEvent('pointermove',{clientX:960+Math.sin(now/200)*400,clientY:500,pointerType:'mouse'}));if(now-started>2500)resolve();else requestAnimationFrame(step);};requestAnimationFrame(step);});
  return {hover,fps:Math.round(1000*(times.length-1)/(times.at(-1)-times[0])),timings:Object.fromEntries(Object.entries(stats).map(([k,s])=>[k,{avgMs:+(s.total/s.count).toFixed(2),maxMs:+s.max.toFixed(2),count:s.count}]))};
 },hover);
 console.log(JSON.stringify(result));
 }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
