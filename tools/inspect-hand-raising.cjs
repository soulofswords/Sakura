const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{chromium}=require('playwright');
const root=process.cwd();function find(dir,predicate){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory()){const v=find(p,predicate);if(v)return v;}else if(predicate(p))return p;}}
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--use-angle=d3d11']});try{const page=await browser.newPage({viewport:{width:720,height:800}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('http://fbx.test/**',async route=>{const pathname=decodeURIComponent(new URL(route.request().url()).pathname);if(pathname.startsWith('/api/'))return route.fulfill({contentType:'application/json',body:route.request().method()==='POST'?'{"saved":true}':'{"repairs":null}'});const f=path.resolve(root,'.'+pathname);if(!f.startsWith(root+path.sep)||!fs.existsSync(f)||!fs.statSync(f).isFile())return route.fulfill({status:404,body:''});const mime={'.html':'text/html','.js':'text/javascript','.json':'application/json','.png':'image/png','.css':'text/css','.wasm':'application/wasm'}[path.extname(f)]||'application/octet-stream';return route.fulfill({contentType:mime,body:fs.readFileSync(f)});});await page.goto('http://fbx.test/static/physics-check.html');await page.waitForFunction(()=>window.viewer?.physics);

const report=await page.evaluate(async()=>{
 const THREE=await import('/static/vendor/three/build/three.module.js');
 const {FBXLoader}=await import('/static/vendor/three/examples/jsm/loaders/FBXLoader.js');
 const response=await fetch('/tools/animation-sources/Hand%20Raising.fbx');const object=new FBXLoader().parse(await response.arrayBuffer(),'/tools/animation-sources/');
 object.updateMatrixWorld(true);const bones=[];object.traverse(b=>{if(b.isBone)bones.push({name:b.name,pos:b.getWorldPosition(b.position.clone()).toArray(),q:b.quaternion.toArray()});});
 const clips=object.animations.map(c=>({name:c.name,duration:c.duration,tracks:c.tracks.map(t=>({name:t.name,type:t.ValueTypeName,count:t.times.length,first:Array.from(t.values.slice(0,4))}))}));

 const clip=object.animations.find(c=>c.tracks.length&&c.duration>0);if(!clip)throw Error('No animated clip');
 const aliases={torso:'Spine',chest:'Spine2',neck:'Neck',head:'Head',leftShoulder:'LeftShoulder',rightShoulder:'RightShoulder',leftArm:'LeftArm',rightArm:'RightArm',leftElbow:'LeftForeArm',rightElbow:'RightForeArm',leftWrist:'LeftHand',rightWrist:'RightHand'};
 const digits=['Thumb','Index','Middle','Ring','Pinky'];
 for(const side of ['left','right'])for(let f=0;f<5;f++)for(let segment=0;segment<3;segment++)aliases[side+'Finger'+f+'_'+segment]=(side==='left'?'Left':'Right')+'Hand'+digits[f]+(segment+1);
 const nodes=Object.fromEntries(Object.entries(aliases).map(([key,name])=>[key,object.getObjectByName('mixamorig'+name)]).filter(([,b])=>b));
 const pos=b=>b.getWorldPosition(new THREE.Vector3());
 const x=pos(nodes.leftArm).sub(pos(nodes.rightArm)).normalize();
 const y=pos(nodes.neck).sub(pos(nodes.torso));y.addScaledVector(x,-y.dot(x)).normalize();
 const z=new THREE.Vector3().crossVectors(x,y).normalize();
 const body=new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(x,y,z)),inverse=body.clone().invert();
 const bindDirections={};
 for(const side of ['left','right']){
  for(const [key,endKey]of [[side+'Shoulder',side+'Arm'],[side+'Arm',side+'Elbow'],[side+'Elbow',side+'Wrist'],[side+'Wrist',side+'Finger2_0']]){
   if(nodes[key]&&nodes[endKey])bindDirections[key]=pos(nodes[endKey]).sub(pos(nodes[key])).normalize().applyQuaternion(inverse).toArray();
  }
  for(let f=0;f<5;f++)for(let segment=0;segment<3;segment++){
   const key=side+'Finger'+f+'_'+segment,end=object.getObjectByName('mixamorig'+(side==='left'?'Left':'Right')+'Hand'+digits[f]+(segment+2));
   if(nodes[key]&&end)bindDirections[key]=pos(end).sub(pos(nodes[key])).normalize().applyQuaternion(inverse).toArray();
  }
 }
 const rest=Object.fromEntries(Object.entries(nodes).map(([key,b])=>[key,b.getWorldQuaternion(new THREE.Quaternion()).invert()]));
 const mixer=new THREE.AnimationMixer(object);mixer.clipAction(clip).play();
 const frames=[],fps=30;
 for(let i=0;i<=Math.ceil(clip.duration*fps);i++){
  const time=Math.min(i/fps,clip.duration-1e-5);mixer.setTime(time);object.updateMatrixWorld(true);
  const rotations={};
  for(const [key,b] of Object.entries(nodes)){
   const delta=b.getWorldQuaternion(new THREE.Quaternion()).multiply(rest[key]);
   rotations[key]=inverse.clone().multiply(delta).multiply(body).normalize().toArray().map(n=>Math.round(n*1e6)/1e6);
  }
  frames.push({time:Number(time.toFixed(6)),rotations});
 }
 return {bones,clips,baked:{version:1,name:'Hand Raising',source:'Hand Raising.fbx',duration:clip.duration,fps,bindDirections,frames}};
});fs.writeFileSync('audit-results/hand-raising-fbx.json',JSON.stringify(report,null,2));fs.mkdirSync('static/assets/animations',{recursive:true});fs.writeFileSync('static/assets/animations/hand-raising.json',JSON.stringify(report.baked));console.log(JSON.stringify({bones:report.bones.slice(0,10),clips:report.clips.map(c=>({name:c.name,duration:c.duration,tracks:c.tracks.slice(0,8)}))}));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
