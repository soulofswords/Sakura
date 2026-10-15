const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
function setup(phase='idle',fail=false){
 const elements=new Map();const element=id=>{if(!elements.has(id))elements.set(id,{textContent:'',classList:{hidden:true,add(){this.hidden=true;},remove(){this.hidden=false;}},addEventListener(){}});return elements.get(id);};
 let selected='kokoro_af_heart',calls=[],release;
 const ctx={document:{getElementById:element},setInterval(){return 1;},clearInterval(){},fetch:async(url,options)=>{calls.push(options?.method||'GET');if(options?.method==='POST'){await new Promise(resolve=>release=resolve);return {ok:!fail,json:async()=>fail?{error:'Download failed'}:{phase:'ready'}};}return {ok:true,json:async()=>({phase,message:'Loading voices'})};}};
 vm.runInNewContext(fs.readFileSync('static/js/voice-runtime.js','utf8').replace('export function','function')+'\nthis.create=createVoiceRuntime;',ctx);
 return {ensure:ctx.create(()=>selected),calls,elements,release:()=>release(),select:value=>selected=value};
}
(async()=>{
 const s=setup(),one=s.ensure(),two=s.ensure();await new Promise(resolve=>setImmediate(resolve));assert.deepEqual(s.calls,['GET','POST'],'Concurrent requests share one initialization');assert.equal(s.elements.get('kokoro-loading-modal').classList.hidden,false);s.release();await Promise.all([one,two]);assert.equal(s.elements.get('kokoro-loading-modal').classList.hidden,true,'Ready popup automatically closes');await s.ensure();assert.equal(s.calls.length,2);
 const r=setup('ready');await r.ensure();assert.deepEqual(r.calls,['GET']);
 const native=setup();native.select('system_en_zira');await native.ensure();assert.deepEqual(native.calls,[],'Explicit Windows voices do not load Kokoro');
 const bad=setup('idle',true),failed=bad.ensure();await new Promise(resolve=>setImmediate(resolve));bad.release();await assert.rejects(failed,/Download failed/);assert.equal(bad.elements.get('kokoro-loading-error').textContent,'Download failed');assert.equal(bad.elements.get('kokoro-loading-close').classList.hidden,false);
 console.log('PASS: local voice preparation, shared initialization, progress popup auto-close, native voice bypass and clear load errors');
})().catch(error=>{console.error(error);process.exitCode=1;});
