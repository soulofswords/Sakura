const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync('static/js/app.js','utf8'),handlers={},buttons=new Map();
const button=id=>{if(!buttons.has(id))buttons.set(id,{disabled:false,hidden:false,textContent:'',setAttribute(){},addEventListener:(event,fn)=>handlers[id]=fn});return buttons.get(id);};
const state={trackingOnly:false,switching:false,mode:button('mode'),start:button('start'),stop:button('stop'),modal:{classList:{remove(){}}},status:{textContent:''},
resumeMic:false,continuousMic:{enabled:true,stop(){this.enabled=false;}},lipSync:{stop(){}},chatReplyGeneration:0,replyController:null,vtuberEnabled:false,vtuberGeneration:0,vtuberQueue:[],reactionsEnabled:true,autoGameEnabled:true,gameActive:true,gameReady:true,
companionCamera:{stop(){}},screenShare:{enabled:false,stop(){}},screenReactBtn:button('reaction'),viewer:{setVtuberTrackingMode(value){state.viewerTracking=value;}},avatarTracking:{stop(){}},setUI(value){state.trackingOnly=value;},stopReader:async()=>{},stopVtuberVoiceChanger:async()=>{},refreshCameras:async()=>{},startDesktopListening:async()=>{},calls:[],
document:{getElementById:button,body:{classList:{contains:()=>false}}},window:{},fetch:async(path,request)=>{const payload=JSON.parse(request.body);state.calls.push({path,...payload});return {ok:true,json:async()=>({tracking_only:payload.enabled})};}};
vm.createContext(state);
const enterStart=source.indexOf("mode.addEventListener('click', async () => {"),enterEnd=source.indexOf("document.getElementById('chat-reader-mode-btn').addEventListener",enterStart);
const restoreStart=source.indexOf("document.getElementById('tracking-restore-ai').addEventListener('click',async()=> {"),restoreEnd=source.indexOf('// A second window',restoreStart);
assert(enterStart>=0&&enterEnd>enterStart&&restoreStart>=0&&restoreEnd>restoreStart);
vm.runInContext(source.slice(enterStart,enterEnd)+source.slice(restoreStart,restoreEnd),state);
(async()=>{await handlers.mode();assert.equal(state.trackingOnly,true);assert.equal(state.calls[0].path,'/api/tracking/mode');assert.equal(state.calls[0].enabled,true);assert.equal(state.continuousMic.enabled,false);assert.equal(state.resumeMic,true);
await handlers['tracking-restore-ai']();assert.equal(state.trackingOnly,false);assert.equal(state.calls.at(-1).enabled,false);assert.equal(state.switching,false);
state.fetch=async()=>({ok:false,json:async()=>({tracking_only:true,error:'Unload failed'})});await handlers.mode();assert.equal(state.trackingOnly,true);assert.equal(state.status.textContent,'Unload failed');assert.equal(state.switching,false);
state.stopReader=async()=>{throw Error('Reader shutdown failed');};await handlers['tracking-restore-ai']();assert.equal(state.switching,false);assert.equal(state.trackingOnly,true);
console.log('PASS: actual mode-button handlers pause through backend before camera selection, restore via backend, retain failed-unload isolation and release busy state');})().catch(e=>{console.error(e);process.exitCode=1;});
