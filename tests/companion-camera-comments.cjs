const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/js/app.js','utf8');
const code=source.slice(source.indexOf('async function reactToCamera()'),source.indexOf('\nfunction showSpeechBubble('));
let requests=0,messages=0,captures=0;
// Pending microphone transcription has priority over unsolicited camera speech.
const ctx={AbortController,Date:{now:()=>200000},companionCamera:{enabled:false,generation:1,snapshot(){captures++;return '/9j/';}},trackingOnly:false,vtuberEnabled:false,aiVtuberStarting:false,chatBusy:false,isRecording:false,lipSync:{isPlaying:false},lastDirectReplyAt:0,lastMicActivity:0,reactionBusy:false,chatReplyGeneration:1,cameraReactionController:null,document:{getElementById:id=>({checked:true,value:id==='companion-camera-mode'?'objects':undefined})},continuousMic:{enabled:false},addMessage(){messages++;},fetch:async()=>{requests++;ctx.companionCamera.enabled=false;ctx.companionCamera.generation++;return{ok:true,json:async()=>({reply:'A stale comment.'})};}};
ctx.companionSleeping=false;
vm.createContext(ctx);vm.runInContext(code,ctx);
ctx.speechRecognitionBusy=0;
(async()=>{
 await ctx.reactToCamera();assert.equal(captures,0);assert.equal(requests,0,'Camera off never captures or sends a frame');
 ctx.companionCamera.enabled=true;ctx.chatBusy=true;await ctx.reactToCamera();assert.equal(requests,0,'Direct chat has priority');
 ctx.chatBusy=false;ctx.speechRecognitionBusy=1;await ctx.reactToCamera();assert.equal(requests,0,'Pending speech has priority');ctx.speechRecognitionBusy=0;
 ctx.chatBusy=false;await ctx.reactToCamera();assert.equal(requests,1);assert.equal(messages,0,'Camera shutdown discards an in-flight comment');assert.equal(ctx.reactionBusy,false);
 console.log('PASS: camera off blocks capture/network, direct chat priority, stale comments discarded');
})().catch(e=>{console.error(e);process.exitCode=1;});
