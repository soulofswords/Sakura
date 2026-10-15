const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('static/js/app.js','utf8');
const fn=source.slice(source.indexOf('async function findCloudModels(){'),source.indexOf('\nlet identityDirty'));
function element(value=''){return {value,children:[],dataset:{},attributes:{},setAttribute(k,v){this.attributes[k]=v;},removeAttribute(k){delete this.attributes[k];},replaceChildren(){this.children=[];},append(value){this.children.push(value);}};}
const elements={'find-cloud-models':element(),'available-cloud-models':element(),'cloud-model-status':element(),'cloud-model':element('gpt-4.1-mini'),'cloud-endpoint':element()};
let calls=[];const ctx={llmProvider:element('openai'),geminiApiKey:element('unsaved-test-key'),geminiModel:element('gemini-test'),document:{getElementById:id=>elements[id],createElement:()=>element()},fetch:async(url,options)=>{calls.push({url,body:JSON.parse(options.body)});return {ok:true,json:async()=>({provider:'openai',models:['gpt-4.1-mini','gpt-test']})};}};
vm.runInNewContext(fn+'\nthis.run=findCloudModels;',ctx);
(async()=>{
 await ctx.run();assert.equal(calls[0].url,'/api/llm/models');assert.equal(calls[0].body.provider,'openai');assert.equal(calls[0].body.api_key,'unsaved-test-key');
 assert.equal(elements['available-cloud-models'].children.length,3);assert.equal(elements['available-cloud-models'].dataset.provider,'openai');assert.equal(elements['find-cloud-models'].disabled,false);
 assert.match(elements['cloud-model-status'].textContent,/2 models found/);assert.ok(!calls.some(c=>c.url==='/api/settings'),'Discovery must not save or change providers');
 ctx.fetch=async()=>({ok:false,json:async()=>({error:'OpenAI HTTP 429: insufficient_quota'})});await ctx.run();assert.match(elements['cloud-model-status'].textContent,/insufficient_quota/);
 assert.equal(elements['find-cloud-models'].attributes['aria-busy'],undefined);console.log('PASS: PC cloud discovery, unsaved key handling, dropdown and error/busy feedback');
})().catch(error=>{console.error(error);process.exitCode=1;});
