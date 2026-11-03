const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const code=fs.readFileSync('static/js/app.js','utf8');
const start=code.indexOf('function extractWakeCommand('),end=code.indexOf('// ─────────────────────────── UI Helpers',start);
let transcript='',media=true,sent=[],agentMode=false,mic={enabled:true,generation:0,stop(){}};
const c={AbortSignal,trackingOnly:false,vtuberEnabled:false,aiVtuberStarting:false,gameActive:false,continuousMic:mic,currentSettings:{wake_word_enabled:false,wake_word:'hey sakura'},wakeCommandDeadline:0,
 interruptFollowupUntil:0,interruptFollowupTimer:null,temporaryFollowupMic:false,speechInputUsed:false,speechRecognitionBusy:0,chatBusy:false,lipSync:null,isSpeechInterrupt:()=>false,clearTimeout(){},nativeWake:{enabled:()=>false},
 screenAudio:{playbackActive:()=>media},listeningStatus:{},chatInput:{},FormData:class{append(){}},showTypingIndicator(){},removeTypingIndicator(){},addMessage(){},console,
 document:{body:{classList:{contains:name=>name==='agent-mode'&&agentMode}}},
 fetch:async()=>({ok:true,json:async()=>({text:transcript})}),handleSendMessage:async()=>sent.push(c.chatInput.value)};
c.companionSleeping=false;
vm.createContext(c);vm.runInContext(code.slice(start,end),c);
(async()=>{
 transcript='The next pro is battery life';await c.sendAudioForSTT({}, {continuous:true});assert.equal(sent.length,0);
 c.wakeCommandDeadline=Date.now()+15000;await c.sendAudioForSTT({}, {continuous:true});assert.equal(sent.length,0,'media cannot use an armed follow-up window');
 transcript='Hey Sakura, how is this drone?';await c.sendAudioForSTT({}, {continuous:true});assert.deepEqual(sent,['how is this drone?']);
 transcript='How is this drone?';await c.sendAudioForSTT({}, {});assert.equal(sent.length,2,'manual microphone still submits');
 media=false;transcript='How are you?';await c.sendAudioForSTT({}, {continuous:true});assert.equal(sent.length,3,'ordinary continuous conversation remains');
 c.currentSettings.wake_word='hello ria';media=true;transcript='Hello Ria, open YouTube';await c.sendAudioForSTT({}, {continuous:true});assert.equal(sent[3],'open YouTube');
 c.gameActive=true;c.currentSettings.game_play_mode='multiplayer';mic.userRequested=true;transcript='How am I doing?';await c.sendAudioForSTT({}, {continuous:true});assert.equal(sent.at(-1),'How am I doing?','Explicit Listen must accept speech without a wake phrase in multiplayer');
 c.currentSettings.wake_word_enabled=true;mic.userRequested=false;transcript='Manual question without wake word';await c.sendAudioForSTT({},{});assert.equal(sent.at(-1),transcript,'Explicit manual microphone bypasses automatic wake-word gate');
 assert.equal(c.speechRecognitionBusy,0,'Recognition lock releases after sending');
 c.wakeCommand=vm.runInNewContext(fs.readFileSync('static/js/sleep-state.js','utf8').replace('export function','function')+';wakeCommand');
 let wakes=0;c.wakeCompanion=()=>{wakes++;c.companionSleeping=false;};c.companionSleeping=true;
 const beforeSleep=sent.length;transcript='Just want to chat? I am all ears and eyes.';await c.sendAudioForSTT({},{continuous:true});assert.equal(sent.length,beforeSleep,'Sleeping speech cannot reach chat');
 transcript='wake up Sakura';await c.sendAudioForSTT({},{continuous:true});assert.equal(wakes,1);assert.equal(sent.length,beforeSleep,'Wake-only phrase performs an action without an LLM request');
 const before=sent.length;agentMode=true;await c.sendAudioForSTT({},{});assert.equal(sent.length,before,'Agent mode blocks Companion speech submission');
 agentMode=false;c.fetch=async()=>({ok:true,json:async()=>{agentMode=true;return {text:'late companion transcript'};}});
 await c.sendAudioForSTT({},{});assert.equal(sent.length,before,'In-flight Companion transcription is discarded after entering Agent mode');
 assert.equal(c.speechRecognitionBusy,0);
 console.log('Media microphone command gate PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
