const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context={};vm.runInNewContext(fs.readFileSync('static/js/utility-request.js','utf8').replace('export function utilityRequest','function utilityRequest')+'\nthis.check=utilityRequest;',context);
for(const text of ['what time is it?','current weather in Mumbai','Start a five-minute timer','Could you please tell me the time?','Open YouTube','latest news','What’s today’s date?'])assert.equal(context.check(text),true,text);
for(const text of ['Can you see this?','What is the weather on my screen?','Explain the news in this video','Do you like my outfit?'])assert.equal(context.check(text),false,text);
const app=fs.readFileSync('static/js/app.js','utf8');assert.ok(app.includes('noVision ? null : await screenShare.snapshot()'));assert.ok(app.includes('screen_frames: noVision ? []'));
console.log('PASS: PC utility requests bypass visual capture; visual questions retain capture');
