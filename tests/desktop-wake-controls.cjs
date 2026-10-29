const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements=new Map(),calls=[],events={};let tick,blocked=false,installed=false,enabled=false;
function element(id){if(!elements.has(id))elements.set(id,{hidden:false,disabled:false,textContent:'',checked:false,dispatchEvent(event){calls.push(['event',event.type]);}});return elements.get(id);}
const context={console,Event:class{constructor(type){this.type=type;}},document:{getElementById:element},setInterval(fn){tick=fn;},window:{addEventListener(name,fn){events[name]=fn;},pywebview:{api:{
 async wake_state(){return {available:true,installed,enabled,status:enabled?'Listening offline':'Wake listener off'};},
 async install_wake_pack(){calls.push(['download']);installed=true;return {installed};},
 async set_wake_listener(value,phrase){calls.push(['listen',value,phrase]);if(value&&!installed)return {error:'Download the optional wake pack first.'};enabled=value;return {enabled,status:enabled?'Listening offline':'Wake listener off'};},
 async pause_wake_listener(value){calls.push(['pause',value]);return true;}
}}}};
vm.runInNewContext(fs.readFileSync('static/js/desktop-wake-controls.js','utf8').replace('export function desktopWakeControls','function desktopWakeControls')+'\nthis.create=desktopWakeControls;',context);
const settings={wake_word_enabled:false,wake_word:'hey sakura'};
(async()=>{
 const browserMic={stop(){calls.push(['browser-mic-stop']);}};
 const controls=context.create({continuousMic:browserMic,settings:()=>settings,blocked:()=>blocked,receive:async text=>{calls.push(['question',text]);},status:text=>calls.push(['status',text])});
 await controls.sync();assert.equal(enabled,false);assert.equal(calls.some(c=>c[0]==='download'),false,'No automatic wake pack download');
 await context.window.receiveDesktopWakeCommand('late audio');assert.equal(calls.some(c=>c[0]==='question'),false,'Disabled wake input rejects late commands');
 settings.wake_word_enabled=true;await controls.sync();assert.equal(enabled,false,'Missing pack never opens the microphone');
 await element('desktop-wake-download').onclick();assert.equal(enabled,true);
 assert.ok(calls.some(c=>c[0]==='browser-mic-stop'),'Browser recorder is released before native wake detection');
 const stops=calls.filter(c=>c[0]==='browser-mic-stop').length;
 browserMic.userRequested=true;await controls.sync();assert.equal(enabled,false,'Explicit mic takes ownership from wake-only listener');
 assert.equal(calls.filter(c=>c[0]==='browser-mic-stop').length,stops,'Periodic sync must not stop explicit listening');
 browserMic.userRequested=false;await controls.sync();assert.equal(enabled,true,'Wake resumes after manual mic ownership is released');
 settings.wake_word='hello computer';await controls.sync();assert.ok(calls.some(c=>c[0]==='listen'&&c[2]==='hello computer'));
 await context.window.receiveDesktopWakeCommand('what time is it');assert.ok(calls.some(c=>c[0]==='question'&&c[1]==='what time is it'));
 assert.deepEqual(calls.at(-1),['pause',false],'Wake resumes after a completed reply');
 await controls.pause(true);await controls.audioActive(true);await controls.pause(false);assert.deepEqual(calls.at(-1),['pause',true],'Audio still pauses wake when chat finishes');await controls.audioActive(false);assert.deepEqual(calls.at(-1),['pause',false]);
 blocked=true;await controls.sync();assert.equal(enabled,false,'Tracking/AI VTuber modes stop microphone wake input');
 assert.equal(await context.window.receiveDesktopWakeCommand('ignore this'),false);assert.deepEqual(calls.at(-1),['pause',false]);
 events['sakura-native-visibility']({detail:{hidden:true}});assert.equal(context.window.sakuraNativeHidden,true);
 events['sakura-native-visibility']({detail:{hidden:false}});assert.equal(context.window.sakuraNativeHidden,false);
 await context.window.stopDesktopWakeFromTray();assert.equal(element('wake-word-toggle').checked,false);
 console.log('PASS: desktop wake opt-in download, custom phrase sync, microphone ownership, reply resume, VTuber guards, tray stop and render visibility');
})().catch(error=>{console.error(error);process.exitCode=1;});
