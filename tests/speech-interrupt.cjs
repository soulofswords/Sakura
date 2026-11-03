const assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{
 const source=fs.readFileSync('static/js/speech-interrupt.js','utf8');
 const {isSpeechInterrupt,createSpeechInterrupt}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
 for(const text of ['stop','wait','Stop speaking!','please stop','wait a second','hey sakura stop','रुको','stop stop','wait, wait!','रुको रुको','please stop stop please'])assert.ok(isSpeechInterrupt(text),text);
 for(const text of ['do not stop','can you tell me when to stop','I will wait for you','stop dancing','the bus stop is nearby','wait what is a compiler'])assert.equal(isSpeechInterrupt(text),false,text);
 assert.ok(isSpeechInterrupt('hello computer wait','hello computer'));
 let callback,allowed=true,stops=0,interrupts=0,creates=0,recognized='',resolve;
 const control=createSpeechInterrupt({allowed:()=>allowed,wakePhrase:()=> 'hey sakura',interrupt:async()=>{interrupts++;control.stop();},
  recognize:async()=>recognized,
  createMic:(receive,status,options)=>{creates++;callback=receive;assert.equal(options.pauseMs,300);return{start:async()=>{},stop:()=>stops++};}});
 await control.start('mic-id');await control.start('mic-id');assert.equal(creates,1,'No duplicate recorder between speech phrases');
 recognized='ordinary conversation';await callback({});assert.equal(interrupts,0,'Ambient speech is never sent as a question');
 recognized='stop';await callback({});assert.equal(interrupts,1);assert.equal(stops,1);
 await callback({});assert.equal(interrupts,1,'Late transcription cannot interrupt a later reply');
 allowed=false;await control.start();assert.equal(creates,1,'Disabled microphone is respected');
 const pending=createSpeechInterrupt({allowed:()=>true,wakePhrase:()=>'',interrupt:()=>interrupts++,recognize:()=>new Promise(r=>resolve=r),createMic:receive=>{callback=receive;return{start:async()=>{},stop(){}};}});
 await pending.start();const task=callback({});pending.stop();resolve('wait');await task;assert.equal(interrupts,1);
 const app=fs.readFileSync('static/js/app.js','utf8');
 assert.match(app,/interruptFollowupUntil=Date\.now\(\)\+15000/);
 assert.match(app,/if\(generation!==chatReplyGeneration\)return/);
 assert.match(app,/void nativeWake\.pause\(companionSleeping\)/);
 console.log('PASS: spoken stop/wait, wake-free command matching, mic opt-in, phrase reuse, stale STT cancellation and follow-up wiring');
})().catch(error=>{console.error(error);process.exitCode=1;});
