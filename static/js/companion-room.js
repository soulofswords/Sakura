import * as THREE from 'three';

export const ROOM_ACTIONS=Object.freeze(['home','desk','mirror','bed','nod','shake_head','stretch']);
const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x);};

// An original, lightweight procedural room. Imported stages are not silently
// treated as navigable furniture: their geometry has no semantic/collision map.
export class CompanionRoom {
 constructor(viewer){this.v=viewer;this.enabled=false;this.pose=null;this.root=null;this.status=()=>{};this.anchors=new Map();}
 available(){const v=this.v;return !!(this.enabled&&this.root===v.model&&!v.live2d&&!v.userTracking&&!v.vtuberTrackingMode&&!v.dance?.active&&v.animationBones?.torso?.bone);}
 capabilities(){return this.available()?ROOM_ACTIONS.filter(action=>(!this.sleeping||action==='home')&&(this.mode!=='imported'||!['desk','mirror','bed'].includes(action)||this.anchors.has(this.stagePath+':'+action))):[];}
 setSleep(value){value=!!value;if(this.sleeping===value)return;this.sleeping=value;if(typeof window!=='undefined')window.dispatchEvent(new CustomEvent('sakura-companion-sleep',{detail:{sleeping:this.sleeping}}));}
 mark(action){
  if(this.mode!=='imported'||!this.available()||!['desk','mirror','bed'].includes(action))throw Error('Enable imported-stage motion and choose a desk, mirror or bed point first.');
  const mesh=this.v.pmxStage?.meshes?.get(this.stageId);if(!mesh)throw Error('The selected PMX stage is no longer loaded.');
  mesh.updateMatrixWorld(true);this.root.updateMatrixWorld(true);
  this.anchors.set(this.stagePath+':'+action,mesh.worldToLocal(this.root.getWorldPosition(new THREE.Vector3())));
  this.status('Marked '+action+' at the character’s current position. Drag back or choose Return home before asking Sakura to visit it.');
 }
 enable(mode='simple'){
  this.disable();const v=this.v;
  this.mode=mode==='imported'?'imported':'simple';
  if(!v.model||v.live2d||!v.animationBones?.torso?.bone)throw Error('Load a rigged PMX or VRM character first.');
  if(v.userTracking||v.vtuberTrackingMode)throw Error('Stop tracking and return to Companion mode first.');
  this.root=v.model;this.base=this.root.position.clone();this.rotation=this.root.quaternion.clone();
  this.homeCamera=v.camera.position.clone();this.homeTarget=v.controls.target.clone();
  this.root.updateMatrixWorld(true);const bounds=new THREE.Box3().setFromObject(this.root),size=bounds.getSize(new THREE.Vector3());
  this.height=size.y;if(!Number.isFinite(this.height)||this.height<=0){this.root=null;throw Error('Character bounds are not ready.');}
  this.floor=bounds.min.y;this.center=bounds.getCenter(new THREE.Vector3());
  this.bodyLocalCenter=this.root.worldToLocal(this.center.clone());this.bodyDepth=size.z;
  if(this.mode==='imported'){
   const stage=v.pmxStage,record=stage?.records?.find(row=>row.id===stage.selected),mesh=stage?.meshes?.get(stage.selected);
   if(!stage?.enabled||!record||!mesh){this.root=null;throw Error('Enable and load a PMX stage, then select it under Stage objects.');}
   this.stageId=record.id;this.stagePath=record.path;this.enabled=true;this.onEnabledChange?.(true);
   this.status('Imported-stage motion ready. Drag the character to a furniture point and mark it. Paths are straight; collision avoidance is not available.');return;
  }
  const h=this.height,room=this.room=new THREE.Group();room.position.set(this.center.x,this.floor,this.center.z);
  const box=(w,y,d,x,cy,z,color)=>{const mesh=new THREE.Mesh(new THREE.BoxGeometry(w,y,d),new THREE.MeshLambertMaterial({color}));mesh.position.set(x,cy,z);room.add(mesh);return mesh;};
  box(h*4,.025*h,h*3.4,0,-.02*h,-.45*h,0xc6bacb);
  box(h*4,h*1.5,.035*h,0,.75*h,-2.1*h,0xe3dbe7);
  // Desk and a screen, bed and pillow, and a deliberately non-reflective mirror.
  box(.9*h,.06*h,.45*h,-1.05*h,.46*h,-.65*h,0x9c7eab);
  for(const x of [-1.43,-.67])for(const z of [-.82,-.48])box(.045*h,.44*h,.045*h,x*h,.22*h,z*h,0x80648f);
  box(.54*h,.32*h,.035*h,-1.05*h,.67*h,-.80*h,0x303c53);
  if(typeof document!=='undefined'){
   this.monitorCanvas=document.createElement('canvas');this.monitorCanvas.width=640;this.monitorCanvas.height=360;
   this.monitorTexture=new THREE.CanvasTexture(this.monitorCanvas);this.monitorTexture.colorSpace=THREE.SRGBColorSpace;
   const display=new THREE.Mesh(new THREE.PlaneGeometry(.52*h,.30*h),new THREE.MeshBasicMaterial({map:this.monitorTexture,toneMapped:false}));
   display.position.set(-1.05*h,.67*h,-.780*h);room.add(display);this.monitorKey='';this.setMonitor({state:'idle',title:'No active task',step:'Ready when you are'});
  }
  box(.75*h,.25*h,1.2*h,1.05*h,.125*h,-.62*h,0xa393b4);
  box(.7*h,.07*h,1.15*h,1.05*h,.285*h,-.62*h,0xeddfe9);
  box(.55*h,.06*h,.22*h,1.05*h,.35*h,-1.02*h,0xffffff);
  box(.56*h,1.04*h,.04*h,-.04*h,.60*h,-1.85*h,0x7e96b0);
  box(.48*h,.96*h,.045*h,-.04*h,.60*h,-1.82*h,0xb7d1de);
  v.scene.add(room);this.enabled=true;this.onEnabledChange?.(true);this.location='home';
  v.controls.target.set(this.center.x,this.floor+h*.55,this.center.z-h*.35);
  v.camera.position.set(this.center.x,this.floor+h*1.25,this.center.z+h*3.2);v.controls.update();
  this.status('Room ready. Ask Sakura to visit the desk, look in the mirror, stretch, or lie on the bed.');
 }
 restoreBones(){if(this.root===this.v.model)for(const [key,value]of Object.entries(this.bones||{})){const bone=this.v.animationBones?.[key]?.bone;if(bone)bone.quaternion.copy(value);}this.bones=null;}
 setMonitor(data){
  this.monitorData=data;this.taskStatus?.(data);if(!this.monitorCanvas)return;
  const key=JSON.stringify(data);if(key===this.monitorKey)return;this.monitorKey=key;
  const c=this.monitorCanvas.getContext('2d');c.fillStyle='#101c28';c.fillRect(0,0,640,360);
  c.fillStyle='#8de0eb';c.font='bold 27px sans-serif';c.fillText('SAKURA · TASK MONITOR',25,44);
  c.fillStyle=data.state==='failed'?'#ff9eaa':data.state==='awaiting_approval'?'#ffd58c':'#b2f4bf';c.font='25px sans-serif';c.fillText(String(data.state||'idle').replaceAll('_',' ').slice(0,30),25,87);
  c.fillStyle='#ffffff';c.font='26px sans-serif';
  const words=String(data.title||'No active task').slice(0,140).split(/\s+/);let line='',y=135;
  for(const word of words){if(c.measureText(line+word).width>580&&line){c.fillText(line,25,y);y+=33;line='';if(y>235)break;}line+=word+' ';}if(y<=235)c.fillText(line,25,y);
  c.fillStyle='#b7cfdf';c.font='23px sans-serif';c.fillText(String(data.step||'').slice(0,43),25,290);
  c.fillText((data.completed_steps||0)+' completed steps',25,332);this.monitorTexture.needsUpdate=true;
 }
 stop(restore=true){this.restoreBones();this.pose=null;this.setSleep(false);if(restore&&this.root===this.v.model&&this.base){this.root.position.copy(this.base);this.root.quaternion.copy(this.rotation);this.location='home';}}
 disable(){
  this.stop();this.enabled=false;this.onEnabledChange?.(false);
  if(this.room){this.room.removeFromParent();this.room.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});this.room=null;}
  this.monitorTexture?.dispose();this.monitorTexture=null;this.monitorCanvas=null;
  if(this.homeCamera&&this.root===this.v.model){this.v.camera.position.copy(this.homeCamera);this.v.controls.target.copy(this.homeTarget);this.v.controls.update();}
  this.root=null;
 }
 act(action){
  if(!this.capabilities().includes(action))return false;
  const rising=action==='home'&&this.sleeping&&(this.location==='bed'||this.pose?.action==='bed'&&this.pose.time>this.pose.duration),oldPosition=this.root.position.clone(),oldRotation=this.root.quaternion.clone();
  let marked;
  if(this.mode==='imported'&&['desk','mirror','bed'].includes(action)){
   const mesh=this.v.pmxStage?.meshes?.get(this.stageId),point=this.anchors.get(this.stagePath+':'+action);
   if(!mesh||!point)return false;
   mesh.updateMatrixWorld(true);marked=mesh.localToWorld(point.clone());
   if(this.root.parent){this.root.parent.updateMatrixWorld(true);this.root.parent.worldToLocal(marked);}
   if(!marked.toArray().every(Number.isFinite)||marked.distanceTo(this.base)>this.height*5){this.status('That point is too far away. Mark a point within five character heights.');return false;}
  }
  this.restoreBones();
  // Always begin locomotion upright; a lying root cannot become a walking rig.
  this.root.quaternion.copy(this.rotation);
  if(this.location==='bed'&&!['home','desk','mirror','bed'].includes(action))this.root.position.copy(this.base);
  const h=this.height,targets={home:[0,0,0],desk:[-1.05*h,0,-.23*h],mirror:[-.04*h,0,-1.30*h],bed:[1.05*h,0,.08*h]};
  const destination=this.base.clone();if(targets[action])destination.add(new THREE.Vector3(...targets[action]));else destination.copy(this.root.position);
  if(marked)destination.copy(marked);
  this.bones=Object.fromEntries(Object.entries(this.v.animationBones).filter(([,e])=>e.bone).map(([k,e])=>[k,e.bone.quaternion.clone()]));
  const duration=Math.max(.8,this.root.position.distanceTo(destination)/h*3.6);
  this.pose={action,time:0,start:this.root.position.clone(),target:destination,duration};
  if(rising){const stand=oldPosition.clone();stand.y=this.base.y;stand.z=this.base.z+.1*h;this.pose.rise={position:oldPosition,rotation:oldRotation,stand};this.pose.start.copy(stand);this.root.quaternion.copy(oldRotation);}
  this.setSleep(action==='bed');
  this.status('Animating: '+action.replaceAll('_',' ')+'. Virtual motion only.');return true;
 }
 update(dt){
  if(!this.enabled)return;
  const v=this.v;
  if(this.mode==='imported'&&(!v.pmxStage?.enabled||!v.pmxStage?.meshes?.has(this.stageId))){this.disable();this.status('Stage motion stopped because the selected PMX stage was removed or disabled.');return;}
  if(this.root!==v.model||v.live2d){this.disable();this.status('Room stopped after changing characters. Enable it again for the new model.');return;}
  if(v.userTracking||v.vtuberTrackingMode){this.stop();return;}
  if(v.dance?.active){this.restoreBones();this.pose=null;return;}
  const p=this.pose;if(!p)return;dt=Number.isFinite(dt)?Math.max(0,Math.min(.05,dt)):0;p.time+=dt;
  if(p.rise){if(p.time<.8){const t=smooth(p.time/.8);this.root.position.lerpVectors(p.rise.position,p.rise.stand,t);this.root.quaternion.slerpQuaternions(p.rise.rotation,this.rotation,t);return;}p.time-=.8;this.root.position.copy(p.rise.stand);p.rise=null;}
  const h=this.height,move=p.time<p.duration&&['home','desk','mirror','bed'].includes(p.action),t=smooth(p.time/p.duration);
  this.root.position.lerpVectors(p.start,p.target,t);this.root.quaternion.copy(this.rotation);
  const bone=(key,x=0,y=0,z=0)=>{const entry=v.animationBones?.[key];if(!entry?.bone)return;entry.bone.quaternion.copy(this.bones[key]);entry.bone.rotateX(x);entry.bone.rotateY(y);entry.bone.rotateZ(z);};
  if(move){
   const gait=Math.sin(p.time*7)*.38,envelope=Math.min(1,t/.15,(1-t)/.15);
   this.root.position.y+=Math.abs(gait)*h*.018*envelope;
   // Face the destination with a bounded turn; model rest orientation is retained.
   const direction=p.target.clone().sub(p.start);if(direction.lengthSq()>.0001)this.root.quaternion.slerp(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),Math.atan2(direction.x,direction.z)),smooth(envelope));
   bone('leftThigh',gait*envelope);bone('rightThigh',-gait*envelope);bone('leftKnee',-Math.max(0,gait)*1.35*envelope);bone('rightKnee',-Math.max(0,-gait)*1.35*envelope);
   bone('leftArm',-gait*.4*envelope);bone('rightArm',gait*.4*envelope);
   return;
  }
  const after=Math.max(0,p.time-p.duration),blend=smooth(after/.6);
  if(p.action==='bed'){
   // Rigid-body placement instead of stretching spine/torso bones.
   const lying=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),-Math.PI/2);
   this.root.quaternion.slerpQuaternions(this.rotation,lying,blend);
   if(this.mode==='simple'){
    const center=new THREE.Vector3(this.center.x+1.05*h,this.floor+.32*h+Math.min(this.bodyDepth,h*.25)/2,this.center.z-.62*h);
    if(this.root.parent){this.root.parent.updateMatrixWorld(true);this.root.parent.worldToLocal(center);}
    const offset=this.bodyLocalCenter.clone().multiply(this.root.scale).applyQuaternion(lying);
    this.root.position.lerpVectors(p.target,center.sub(offset),blend);
   }
  }else if(p.action==='desk'){
   this.root.rotateY(Math.PI*blend);bone('leftArm',.25*blend,0,(v.vrm?1:-1)*.35*blend);bone('rightArm',.25*blend,0,(v.vrm?-1:1)*.35*blend);
   bone('leftElbow',0,-.7*blend);bone('rightElbow',0,.7*blend);bone('leftWrist',Math.sin(after*12)*.05*blend);bone('rightWrist',-Math.sin(after*12)*.05*blend);
  }else if(p.action==='mirror'){this.root.rotateY(Math.PI*blend);}
  else{
   const phase=Math.max(0,Math.min(1,p.time/3)),wave=Math.sin(phase*Math.PI*4)*Math.sin(phase*Math.PI)*.12;
   if(p.action==='nod')bone('head',wave);if(p.action==='shake_head')bone('head',0,wave);
   if(p.action==='stretch'){const lift=Math.sin(phase*Math.PI)*.8;bone('leftArm',0,0,(v.vrm?-1:1)*lift);bone('rightArm',0,0,(v.vrm?1:-1)*lift);}
   if(p.time>=3){this.restoreBones();this.pose=null;this.status('Motion finished.');}return;
  }
  if(after>8||p.action==='home'){this.location=p.action;this.restoreBones();this.pose=null;this.status('At '+p.action+'. Ask to return home when ready.');}
 }
}

export function installCompanionRoom(viewer){
 if(window.SAKURA_EDITION==='vtuber')return;
 const room=new CompanionRoom(viewer);viewer.companionRoom=room;
 const card=document.createElement('section');card.className='studio-card';card.id='companion-room-controls';
 card.innerHTML='<h3>Companion room & body</h3><label><input type="checkbox" role="switch"> Let Sakura animate her body and interact with a room</label><label>Room source<select data-room-source><option value="simple">Simple room</option><option value="imported">Selected imported PMX stage</option></select></label><div data-room-points hidden><p>Load and select a PMX stage under Stage objects. Enable room motion, drag the character to a destination, then mark it. These are straight walking paths without collision avoidance; keep paths clear.</p><button type="button" data-room-mark="desk">Mark desk position</button><button type="button" data-room-mark="mirror">Mark mirror position</button><button type="button" data-room-mark="bed">Mark bed position</button><p>Points last for this app session and follow stage position, scale and rotation.</p></div><p>Rigged PMX/VRM only. Explicit room commands work in Friend and Teacher modes. Say “wake up Sakura” to leave sleep. Typing is an animation; mirrors do not supply vision. Tracking takes priority. Your custom hello wave is preserved.</p><button type="button" data-room-home>Stop & return home</button><p role="status">Off. No room motion.</p>';
 const toggle=card.querySelector('input'),status=card.querySelector('[role=status]');room.status=text=>status.textContent=text;
 const taskStatus=document.createElement('p');taskStatus.setAttribute('role','status');taskStatus.dataset.roomTaskStatus='';card.append(taskStatus);
 room.taskStatus=data=>{taskStatus.textContent=(data.title||'No active task')+' · '+(data.state||'idle')+(data.step?' · '+data.step:'');};
 room.onEnabledChange=value=>toggle.checked=value;
 const source=card.querySelector('[data-room-source]');
 toggle.onchange=()=>{try{if(toggle.checked)room.enable(source.value);else{room.disable();room.status('Off. Original placement restored.');}}catch(error){toggle.checked=false;room.status(error.message);}};
 source.onchange=()=>{card.querySelector('[data-room-points]').hidden=source.value!=='imported';if(room.enabled){room.disable();toggle.checked=false;room.status('Room source changed. Enable motion to set the current home position.');}};
 for(const button of card.querySelectorAll('[data-room-mark]'))button.onclick=()=>{try{room.mark(button.dataset.roomMark);}catch(error){room.status(error.message);}};
 card.querySelector('[data-room-home]').onclick=()=>{room.stop();room.status('Stopped. Original placement restored.');};
 let monitorBusy=false,localTask=null;
 const localProgress=event=>{localTask=event.detail?.active?{state:'working',title:'Answering your question',step:'Companion reply',completed_steps:0}:null;if(room.enabled&&room.monitorCanvas&&localTask)room.setMonitor(localTask);};
 window.addEventListener('sakura-task-progress',localProgress);
 const endLocal=()=>{localTask=null;};document.getElementById('interrupt-btn')?.addEventListener('click',endLocal);
 const refreshMonitor=async()=>{
  if(monitorBusy||!room.enabled||!room.monitorCanvas||document.visibilityState==='hidden')return;
  if(document.body.classList.contains('agent-mode'))localTask=null;
  monitorBusy=true;
  try{const response=await fetch('/api/features/task-monitor',{signal:AbortSignal.timeout(5000)});if(!response.ok)throw Error('Unavailable');const state=await response.json();if(room.enabled&&room.monitorCanvas)room.setMonitor(state.state==='idle'&&localTask?localTask:state);}
  catch{if(room.enabled&&room.monitorCanvas)room.setMonitor(localTask||{state:'unavailable',title:'Task status unavailable',step:'Check Agent mode'});}
  finally{monitorBusy=false;}
 };
 const monitorTimer=setInterval(refreshMonitor,2000);
 const mount=()=>{const host=document.querySelector('[data-companion-content="background"]');if(host&&card.parentNode!==host)host.append(card);};mount();
 const observer=new MutationObserver(mount);observer.observe(document.body,{childList:true,subtree:true});
 viewer.renderer.domElement.addEventListener('pointerdown',()=>{if(room.pose)room.stop();});
 window.addEventListener('pagehide',()=>{clearInterval(monitorTimer);document.getElementById('interrupt-btn')?.removeEventListener('click',endLocal);window.removeEventListener('sakura-task-progress',localProgress);observer.disconnect();room.disable();},{once:true});
 return room;
}
