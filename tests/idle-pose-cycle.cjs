const fs=require('fs'),assert=require('assert/strict');
// Pure-JS harness: no browser needed, the module only touches plain objects.
const src=fs.readFileSync('static/js/idle-breathing.js','utf8').replace(/^import .*$/m,'').replace(/export /g,'');
const mod=new Function(src+'; return {restoreIdleBreathing, applyIdleBreathing};')();
const BONES=['torso','chest','neck','head','leftArm','rightArm','leftElbow','rightElbow','leftWrist','rightWrist'];
const makeViewer=over=>{const v={activity:'idle',live2d:false,model:{position:{x:0,y:0,z:0}},physics:{allowIdleSleep:true},
 animationBones:Object.fromEntries(BONES.map(k=>[k,{bone:{rotation:{x:.1*k.length,y:.05,z:.02,order:'YXZ'}}}])),...over};return v;};
const snapshot=v=>Object.fromEntries(BONES.map(k=>[k,[v.animationBones[k].bone.rotation.x,v.animationBones[k].bone.rotation.y,v.animationBones[k].bone.rotation.z]]));
const run=(v,frames,dt=.033)=>{let t=0;for(let i=0;i<frames;i++){t+=dt;mod.restoreIdleBreathing(v);v._fakeBaseline=snapshot(v);mod.applyIdleBreathing(v,dt,t);}return t;};
(async()=>{
 // 1. The pose cycle must actually fire, and each pose must move real bones.
 let v=makeViewer(),moved=0,poses=0,maxDelta=0,seen=new Set();
 let t=0;const dt=.033;
 for(let i=0;i<Math.ceil(400/dt);i++){
  t+=dt;mod.restoreIdleBreathing(v);
  const before=snapshot(v);
  mod.applyIdleBreathing(v,dt,t);
  const after=snapshot(v);
  if(v._idlePose&&v._idlePose.phase!=='rest'){poses++;if(v._idlePose.pose)seen.add(v._idlePose.pose.name);}
  for(const k of BONES)for(const j of [0,1,2]){const d=Math.abs(after[k][j]-before[k][j]);if(d>1e-7){moved++;maxDelta=Math.max(maxDelta,d);}}
 }
 assert.ok(poses>0,'the idle pose cycle never fired within 400s');
 assert.ok(moved>0,'no bone was ever written');
 assert.ok(maxDelta>0.01,`the pose layer is invisible: max per-frame delta ${maxDelta.toFixed(4)}`);
 assert.ok(seen.size>=3,`only ${seen.size} distinct idle poses were reachable: ${[...seen]}`);
 assert.ok(maxDelta<0.35,`a single frame moved a bone ${maxDelta.toFixed(2)} rad — that is a snap, not an idle`);

 // 2. A pose must leave the rig exactly as it found it. Rest and hold lengths
 //    are deliberately random, so this follows the state machine to its own
 //    boundaries instead of a wall clock: a fixed 120s lands mid-pose about
 //    half the time, which is a flake and not a bug.
 v=makeViewer();const rest=snapshot(v);t=0;const trail=[];
 const until=(phase,limit=240)=>{let guard=0;
  while((!v._idlePose||v._idlePose.phase!==phase)&&guard++<Math.ceil(limit/dt)){t+=dt;mod.restoreIdleBreathing(v);mod.applyIdleBreathing(v,dt,t);
   const now=v._idlePose?.phase;if(now&&trail[trail.length-1]!==now)trail.push(now);}
  assert.equal(v._idlePose?.phase,phase,`the cycle never reached ${phase} within ${limit}s`);};
 until('in');
 assert.ok(v._idlePose.pose,'the cycle entered a pose without choosing one');
 until('rest');
 assert.equal(trail.join('>'),'rest>in>hold>out>rest',`the pose cycle took an unexpected path: ${trail.join('>')}`);
 assert.deepEqual(Object.keys(v._idlePose.weights),[],'pose weights leaked after returning to rest');
 // After one final restore the rig must be exactly where an idle rig started.
 mod.restoreIdleBreathing(v);
 assert.deepEqual(snapshot(v),rest,'the idle pose layer permanently deformed the rig');

 // 3. Root translation is forbidden (the module header says rotation only).
 v=makeViewer();t=0;for(let i=0;i<Math.ceil(200/dt);i++){t+=dt;mod.restoreIdleBreathing(v);mod.applyIdleBreathing(v,dt,t);
  assert.equal(v.model.position.x,0,'idle moved the model root');}

 // 4. Every blocking state must write nothing at all.
 const BLOCKED=[{dance:{active:true}},{activity:'talking'},{live2d:true},{remoteCollab:true},{userTracking:true,companionTracking:false},{chatReaderMotion:true}];
 for(const over of BLOCKED){
  const blocked=makeViewer(over);const before=snapshot(makeViewer(over));
 t=0;for(let i=0;i<Math.ceil(60/dt);i++){t+=dt;mod.restoreIdleBreathing(blocked);mod.applyIdleBreathing(blocked,dt,t);}
  assert.deepEqual(snapshot(blocked),before,`${JSON.stringify(Object.keys(over))}: idle still moved the rig while blocked`);
 }

 // 5. A model with no arm bones must simply stay still instead of throwing.
 const arms=makeViewer();for(const k of ['leftArm','rightArm','leftElbow','rightElbow','leftWrist','rightWrist'])delete arms.animationBones[k];
 t=0;for(let i=0;i<Math.ceil(120/dt);i++){t+=dt;mod.restoreIdleBreathing(arms);mod.applyIdleBreathing(arms,dt,t);}
 console.log(`PASS: idle pose cycle reaches ${seen.size} poses, peaks at ${maxDelta.toFixed(3)} rad/frame, restores the rig exactly, never moves the root, and stays silent in all ${BLOCKED.length} blocked states.`);
})().catch(e=>{console.error(e);process.exitCode=1;});
