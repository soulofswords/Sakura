const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let now=0,enabled=true,busy=false,calls=0;
const ctx={Date:{now:()=>now},AbortController,setTimeout,clearTimeout};
vm.runInNewContext(fs.readFileSync('static/js/screen-memory.js','utf8').replace('export default class ScreenMemory','class ScreenMemory')+'\nthis.Memory=ScreenMemory',ctx);
(async()=>{
 const share={get enabled(){return enabled;},observationFrames:()=>['first','second','last']};
 const memory=new ctx.Memory(share,()=>enabled,()=>busy,async(url,options)=>{
  calls++;const payload=JSON.parse(options.body);assert.equal(payload.screen_observation,true);
  assert.deepEqual(payload.screen_frames,['first','second','last']);assert.equal(payload.screen_image,'last');
  return {ok:true};
 });
 enabled=false;await memory.tick();assert.equal(calls,0);
 enabled=true;busy=true;await memory.tick();assert.equal(calls,0);
 busy=false;await memory.tick();assert.equal(calls,1);
 now=10000;await memory.tick();assert.equal(calls,1);
 now=20000;await memory.tick();assert.equal(calls,2);
 enabled=false;now=40000;await memory.tick();assert.equal(calls,2);
 console.log('PASS: silent screen sampling requires active sharing, yields to conversation and is rate limited');
})().catch(e=>{console.error(e);process.exitCode=1;});
