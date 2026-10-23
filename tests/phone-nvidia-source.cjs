const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const app=fs.readFileSync('static/js/app.js','utf8');
const begin=app.indexOf('    const updateFaceSource = '),end=app.indexOf("    faceTrackingSource.addEventListener('change'",begin);
async function check(phone,requested,expected){
 let broadcastClicks=0,started=0,selected;
 const el=()=>({value:'',setAttribute(){}}),nodes={};
 const source=el();source.value=requested;
 const context={camera:{value:phone?'sakura-mobile':'webcam-id'},avatarTracking:{remoteActive:phone,enabled:false,setFaceSource(v){selected=v;}},faceTrackingSource:source,companionFaceTrackingSource:el(),localStorage:{setItem(){}},nvidiaRtxToggle:el(),faceTrackingHelp:el(),faceSourceHelp:{},vbridgerStatus:el(),trackingBackend:{value:'mediapipe'},trackingBackendHelp:el(),backendHelp:{nvidia_gpu:''},graphicsRenderer:()=>'',cameraStatus:el(),document:{getElementById(id){return nodes[id]??=(id==='tracking-broadcast-camera'?{click(){broadcastClicks++;}}:el());}},fetch:async()=>{started++;return{ok:true,json:async()=>({})};}};
 vm.createContext(context);vm.runInContext(app.slice(begin,end)+'\nupdateFaceSource(true);',context);await new Promise(setImmediate);
 assert.equal(selected,expected);assert.equal(context.camera.value,phone?'sakura-mobile':'webcam-id');assert.equal(broadcastClicks,phone?0:1);assert.equal(started,phone?1:0);
}
(async()=>{await check(true,'nvidia_broadcast','nvidia_ar');await check(true,'nvidia_expressionapp','nvidia_ar');await check(false,'nvidia_broadcast','nvidia_broadcast');console.log('Phone NVIDIA switch preserves camera, initializes native input; webcam Broadcast selection preserved.');})().catch(e=>{console.error(e);process.exit(1);});

// Exercise the PC request handler with an already-streaming phone and no
// duplicate phone tracking-start command.
const mobile=fs.readFileSync('static/js/mobile-link.js','utf8');
const handler=mobile.slice(mobile.indexOf("    window.addEventListener('sakura-phone-tracking-requested'"),mobile.indexOf('    const trackingStatus='));
let listener,tracking=[];const tracker={};
const resume={window:{addEventListener(name,fn){listener=fn;}},getTracker:()=>tracker,getViewer:()=>({setVtuberTrackingMode(v){tracking.push(v);},setUserTracking(v){tracking.push(v);}}),HeadPoseFilter:class{},performance:{now:()=>100}};
vm.createContext(resume);vm.runInContext('let remote=false,remoteKind="",filter=null,remoteSamples=0,remoteStarted=0;'+handler,resume);
listener({detail:{enabled:true}});assert.equal(tracker.remoteActive,true);assert.deepEqual(tracking,[true,true]);
listener({detail:{enabled:false}});assert.equal(tracker.remoteActive,false);assert.deepEqual(tracking,[true,true,false,false]);
console.log('PC Start and Stop synchronize remote frame acceptance after reconnect.');
