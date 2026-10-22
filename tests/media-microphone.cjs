const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const code=fs.readFileSync('static/js/app.js','utf8');
const start=code.indexOf('function extractWakeCommand('),end=code.indexOf('// ─────────────────────────── UI Helpers',start);
let transcript='',media=true,sent=[];
const c={trackingOnly:false,vtuberEnabled:false,aiVtuberStarting:false,currentSettings:{wake_word_enabled:false,wake_word:'hey sakura'},wakeCommandDeadline:0,
 interruptFollowupUntil:0,interruptFollowupTimer:null,temporaryFollowupMic:false,speechInputUsed:false,chatBusy:false,lipSync:null,isSpeechInterrupt:()=>false,clearTimeout(){},nativeWake:{enabled:()=>false},
 screenAudio:{playbackActive:()=>media},listeningStatus:{},chatInput:{},FormData:class{append(){}},showTypingIndicator(){},removeTypingIndicator(){},addMessage(){},console,
 fetch:async()=>({ok:true,json:async()=>({text:transcript})}),handleSendMessage:async()=>sent.push(c.chatInput.value)};
vm.createContext(c);vm.runInContext(code.slice(start,end),c);
(async()=>{
 transcript='The next pro is battery life';await c.sendAudioForSTT({}, {continuous:true});assert.equal(sent.length,0);
 c.wakeCommandDeadline=Date.now()+15000;await c.sendAudioForSTT({}, {continuous:true});assert.equal(sent.length,0,'media cannot use an armed follow-up window');
 transcript='Hey Sakura, how is this drone?';await c.sendAudioForSTT({}, {continuous:true});assert.deepEqual(sent,['how is this drone?']);
 transcript='How is this drone?';await c.sendAudioForSTT({}, {});assert.equal(sent.length,2,'manual microphone still submits');
 media=false;transcript='How are you?';await c.sendAudioForSTT({}, {continuous:true});assert.equal(sent.length,3,'ordinary continuous conversation remains');
 c.currentSettings.wake_word='hello ria';media=true;transcript='Hello Ria, open YouTube';await c.sendAudioForSTT({}, {continuous:true});assert.equal(sent[3],'open YouTube');
 console.log('Media microphone command gate PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
