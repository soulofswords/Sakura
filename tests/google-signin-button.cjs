const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/assets/agent.html','utf8');
const handler=source.split('\n').find(line=>line.startsWith("$('calendar-connect').onclick="));
(async()=>{
 for(const mode of ['calendar','workspace']){
  const elements={'calendar-connect':{},'google-services':{value:mode},status:{}};let calls=[],pending,polled;
  const ctx={$:id=>elements[id],state:{calendar:{configured:true}},calendarPollTimer:null,clearInterval(){},setInterval(fn){polled=fn;return 1;},announce(){},refresh:async()=>{},api:async(path,args)=>{calls.push([path,args]);return {connected:true,workspace_connected:true};},perform(fn){pending=fn();return pending;}};
  vm.runInNewContext(handler,ctx);elements['calendar-connect'].onclick();await pending;await Promise.resolve();
  assert.equal(calls[0][0],'calendar/connect');assert.equal(calls[0][1].workspace,mode==='workspace');
  assert.ok(elements.status.textContent.includes('opened in your browser'));
  await polled();assert.equal(calls[1][0],'calendar/status');
 }
 console.log('PASS: sign-in button requests both service selections and polls connection without ReferenceError');
})().catch(e=>{console.error(e);process.exitCode=1;});
