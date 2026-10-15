const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
let tick,listener,requests=0,active=true,dismissed=false;
const paragraph={},panel={hidden:true,setAttribute(){},querySelector:()=>paragraph,addEventListener:(name,fn)=>listener=fn,remove(){}};
const ctx={document:{createElement:()=>panel,body:{appendChild(){}}},window:{addEventListener(){}},Date,setInterval:fn=>{tick=fn;return 1;},clearInterval(){},fetch:async(url,options)=>{
 requests++;if(options){const body=JSON.parse(options.body);assert.equal(body.id,'id123');dismissed=true;return{ok:true};}
 return{ok:true,json:async()=>({items:dismissed?[]:[{id:'id123',status:'ringing',kind:'timer',label:'5 second timer'}]})};
}};
vm.runInNewContext(fs.readFileSync('static/js/assistant-reminders.js','utf8').replace('export function','function')+'\nthis.install=installReminders;',ctx);
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 ctx.install(()=>active);await settle();assert.equal(panel.hidden,false);assert.match(paragraph.textContent,/Timer finished/);
 await listener({target:{dataset:{action:'dismiss'}}});assert.equal(panel.hidden,true);
 const before=requests;active=false;await tick();assert.equal(requests,before,'Tracking mode never polls Companion reminders');
 console.log('PASS: due alert, safe text presentation, dismiss and tracking isolation without TTS');
})().catch(e=>{console.error(e);process.exitCode=1;});
