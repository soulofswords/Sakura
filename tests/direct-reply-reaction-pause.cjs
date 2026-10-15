const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/js/app.js','utf8');
const code=source.slice(source.indexOf('async function reactToScreen('),source.indexOf('\nfunction showSpeechBubble('));
let requests=0,messages=0;
const now=100000;
const context={Date:{now:()=>now},trackingOnly:false,lastDirectReplyAt:now-1000,
 vtuberEnabled:false,lastCoHostSpeech:0,autoGameEnabled:false,gameActive:false,
 reactionsEnabled:true,reactionBusy:false,chatBusy:false,isRecording:false,lastMicActivity:0,
 lipSync:{isPlaying:false},chatReplyGeneration:1,continuousMic:{enabled:false},viewer:null,
 listeningStatus:{},document:{getElementById:()=>({checked:false})},
 screenShare:{enabled:true,snapshot:async()=>'/9j/image',recentFrames:()=>[]},
 fetch:async()=>{requests++;context.lastDirectReplyAt=now;return{ok:true,json:async()=>({reply:'An unsolicited second reply.'})};},
 addMessage(){messages++;},hideSpeechBubble(){}};
vm.createContext(context);vm.runInContext(code,context);
(async()=>{
 await context.reactToScreen();assert.equal(requests,0,'Direct answer gives the conversation quiet time');
 context.lastDirectReplyAt=now-40000;
 await context.reactToScreen();assert.equal(requests,1);
 assert.equal(messages,0,'A direct reply arriving during background inference cancels the unsolicited message');
 assert.equal(context.reactionBusy,false,'Reaction lock released after cancellation');
 console.log('PASS: direct replies pause screen reactions and cancel in-flight unsolicited replies');
})().catch(error=>{console.error(error);process.exitCode=1;});
