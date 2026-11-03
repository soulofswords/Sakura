const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('static/js/app.js','utf8');
const classes=new Set(),calls=[];
const classList={contains:n=>classes.has(n),toggle(n,on){on?classes.add(n):classes.delete(n);},remove:n=>classes.delete(n),add:n=>classes.add(n)};
const c={document:{body:{classList},documentElement:{classList}},trackingOnly:false,agentModeButton:{setAttribute(){}},
 continuousMic:{stop(){calls.push('continuous stopped');}},speechInterrupt:{stop(){calls.push('interrupt stopped');}},
 interruptFollowupTimer:null,clearTimeout(){},chatReplyGeneration:0,replyController:{abort(){calls.push('reply aborted');}},
 mediaRecorder:{state:'recording',stop(){this.state='inactive';calls.push('manual stopped');}},isRecording:true,micBtn:{classList},
 nativeWake:{async sync(force){assert.equal(force,true);assert(classes.has('agent-mode'));calls.push('wake disabled');}},
 agentFrame:{src:'about:blank'},window:{applyLibraryMode:async full=>{c.restoredFull=full;}},chatPanel:{classList},chatBubbleBtn:{classList},
 requestAnimationFrame(){}};
vm.createContext(c);
const start=source.indexOf('const setAgentMode=async enabled=>{'),end=source.indexOf('window.sakuraSetAgentMode=setAgentMode;',start);
assert(start>=0&&end>start);
vm.runInContext(source.slice(start,end)+'\nthis.setAgentMode=setAgentMode;',c);
(async()=>{await c.setAgentMode(true);assert.equal(c.agentFrame.src,'/agent?embedded=1');assert.equal(c.isRecording,false);
 assert.deepEqual(calls,['continuous stopped','interrupt stopped','reply aborted','manual stopped','wake disabled']);
 assert.equal(c.chatReplyGeneration,1);await c.setAgentMode(false);assert.equal(c.agentFrame.src,'about:blank');
 assert.equal(calls.length,5,'Returning to Companion does not silently restart continuous recording');assert.equal(c.restoredFull,true);classes.add('desktop-companion');await c.setAgentMode(true);await c.setAgentMode(false);assert.equal(c.restoredFull,false,'Agent returns to the compact mode it was entered from');
 console.log('PASS: Agent transition stops all Companion listeners and aborts pending reply');
})().catch(error=>{console.error(error);process.exitCode=1;});
