const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const wake=vm.runInNewContext(fs.readFileSync('static/js/sleep-state.js','utf8').replace('export function','function')+';wakeCommand');
assert.equal(wake('wake up Sakura').wake,true);
assert.equal(wake('Hey Ria, Copy EXACT Case','hey ria').command,'Copy EXACT Case');
assert.equal(wake('ordinary chatter').wake,false);
assert.equal(wake('they said wake up sakura').wake,false);
const app=fs.readFileSync('static/js/app.js','utf8').replace(/\r/g,'');
const wrapper=app.split('\n').find(line=>line.startsWith('const speakPhrases='));
let calls=0;const context={companionSleeping:true,runSpeechPhrases:()=>{calls++;return Promise.resolve();},Promise};
vm.createContext(context);vm.runInContext(wrapper+';this.speak=speakPhrases;',context);
(async()=>{
 await context.speak('Do not speak',()=>{},()=>{});assert.equal(calls,0,'Sleep blocks TTS generation');
 context.companionSleeping=false;await context.speak('Awake',()=>{},()=>{});assert.equal(calls,1);
 for(const name of ['pollVtuberChat()','reactToScreen(initialCheck = false)','reactToCamera()'])assert.ok(app.includes('async function '+name+' {\n    if(companionSleeping)return;'),'Sleep gates '+name);
 assert.ok(app.includes('new ScreenMemory(screenShare,()=>!trackingOnly&&!companionSleeping'));
 console.log('PASS: deterministic wake recognition, preserved command casing, sleeping speech/proactive gates and awake speech recovery.');
})().catch(error=>{console.error(error);process.exitCode=1;});
