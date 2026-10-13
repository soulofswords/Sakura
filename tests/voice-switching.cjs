const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');
const source=fs.readFileSync('static/js/app.js','utf8');
const selection=source.slice(source.indexOf('async function applyVoiceById('),source.indexOf('async function testCurrentVoice('));
const saving=source.slice(source.indexOf('async function saveVoiceSettings('),source.indexOf('// ── RVC Upload'));
let releases=[];let sent=[];
const context={fetch:async(url,options)=>{sent.push(JSON.parse(options.body));await new Promise(resolve=>releases.push(resolve));return {ok:true,json:async()=>({ok:true,settings:{selected_voice:sent.at(-1).selected_voice}})}},
    chatBusy:false,reactionBusy:false,flashMsg(){},addMessage(){},voiceSaveMsg:{},lipSync:{stop(){}},
    allRvcModels:[],allVoicePresets:[{id:'one',pitch:'+3Hz',rate:'+5%'},{id:'two',pitch:'+0Hz',rate:'-5%'}],
    rvcPitchSlider:{value:'0'},rvcIndexRateSlider:{value:'0.75'}};
vm.runInNewContext("let chatReplyGeneration=0;let currentVoiceId='one';let currentSettings={};let voiceSaveQueue=Promise.resolve();function selectVoiceCard(id){currentVoiceId=id;}"+selection+saving+'\nthis.apply=applyVoiceById;this.settings=()=>currentSettings;',context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 const first=context.apply('one');const second=context.apply('two');await tick();
 assert.equal(sent.length,1);assert.equal(sent[0].selected_voice,'one');assert.equal(sent[0].tts_pitch,'+3Hz');assert.equal(sent[0].tts_rate,'+5%');assert.equal(sent[0].rvc_model,'');
 releases.shift()();await tick();assert.equal(sent.length,2);assert.equal(sent[1].selected_voice,'two');
 releases.shift()();await Promise.all([first,second]);assert.equal(context.settings().selected_voice,'two');
 context.chatBusy=true;await context.apply('one');assert.equal(sent.length,2,'voice cannot change during a generated reply');
 context.chatBusy=false;context.lipSync.isPlaying=true;await context.apply('one');assert.equal(sent.length,2,'voice cannot change during playback');
 context.lipSync.isPlaying=false;
 console.log('PASS: selecting a voice applies it, preserves preset tuning, clears RVC, and orders rapid switches');
})().catch(e=>{console.error(e);process.exitCode=1;});
