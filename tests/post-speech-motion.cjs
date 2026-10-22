const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const THREE=require('../static/vendor/three/build/three.cjs');
const gestureSource=fs.readFileSync('static/js/speech-gesture.js','utf8').replace(/^export /gm,'');
const {speechGestureWeights}=vm.runInNewContext(gestureSource+'\n({speechGestureWeights})',{});
const src=fs.readFileSync('static/js/model-viewer.js','utf8').replace(/\r\n/g,'\n');
const animateBase=new Function('delta','elapsed','speechGestureWeights',src.match(/_animateCharacter\(delta, elapsed\) \{([\s\S]*?)\n    \}\n\n    _visibleModelBounds/)[1]);
const animate=function(delta,elapsed){return animateBase.call(this,delta,elapsed,speechGestureWeights);};
function viewer(){return {model:{},activity:'talking',talkBlend:0,thinkBlend:0,speechLevel:.6,physicsBoost:0,physics:{windStrength:0},animationBones:Object.fromEntries(['torso','chest','neck','head'].map(k=>[k,{bone:new THREE.Bone(),rest:new THREE.Euler()}])),expressionWeights:{},emotion:'friendly'};}
for(const mode of ['gemini','local']){
 const v=viewer();for(let i=0;i<60;i++)animate.call(v,1/60,i/60,speechGestureWeights);v.activity='idle';
 for(let i=0;i<180;i++)animate.call(v,1/60,1+i/60,speechGestureWeights);
 assert.ok(v.conversationMotion.settling);assert.ok(v.conversationMotion.settleTime>0);assert.equal(v.physics.allowIdleSleep,false);
 for(let i=0;i<360;i++)animate.call(v,1/60,4+i/60);
 assert.equal(v.conversationMotion.settling,false);assert.ok(Math.abs(v.animationBones.torso.motion.z)>.001);assert.equal(v.physics.allowIdleSleep,true);
 let low=Infinity,high=-Infinity;
 for(let i=0;i<720;i++){animate.call(v,1/60,10+i/60);const lean=v.animationBones.torso.motion.z;low=Math.min(low,lean);high=Math.max(high,lean);}
 assert.ok(low<-.02&&high>.02,'AI companion keeps gently shifting left and right after the settle animation ends');
 const side=v.conversationMotion.settleSide;v.activity='talking';animate.call(v,1/60,10);v.activity='idle';animate.call(v,1/60,11);assert.equal(v.conversationMotion.settleSide,-side);
}
const tracked=viewer();tracked.userTracking=true;let calls=0;tracked.avatarRetarget={apply(){calls++;}};animate.call(tracked,1/60,0);assert.equal(calls,1);assert.equal(tracked.conversationMotion,undefined);
const vt=viewer();vt.vtuberTrackingMode=true;animate.call(vt,1/60,0);vt.activity='idle';animate.call(vt,1/60,1);assert.equal(vt.conversationMotion,undefined,'VTuber voice playback cannot create AI conversational gestures');
console.log('PASS: AI post-speech lean alternates, settles, wakes physics, and leaves VTuber retargeting untouched');
