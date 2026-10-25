const fs=require('node:fs');
const assert=require('node:assert/strict');
const EyeTracking=new Function(fs.readFileSync('static/js/eye-tracking.js','utf8')
    .replace('export default class EyeTracking','class EyeTracking')+';return EyeTracking;')();
global.location={href:'http://127.0.0.1:8766/?desktop=1',protocol:'http:'};
const listeners=new Map();
global.window={screen:{width:1920,height:1080,isExtended:false},addEventListener:(name,fn)=>listeners.set(name,fn),removeEventListener:(name)=>listeners.delete(name)};
const sockets=[];
global.WebSocket=class {
    constructor(url){this.url=String(url);sockets.push(this);}
    close(){this.closed=true;this.onclose?.();}
    sample(x,y){this.onmessage?.({data:JSON.stringify({x,y})});}
};
let finishOldRead;
global.fetch=()=>new Promise(resolve=>{finishOldRead=()=>resolve({ok:true,json:async()=>({x:-1,y:-1})});});
const viewer={setEyeTrackingTarget(x,y){this.target={x,y};},clearEyeTracking(){this.target=null;}};
const tracker=new EyeTracking(viewer,()=>{});
(async()=>{
    tracker.start();
    assert.equal(sockets[0].url,'ws://127.0.0.1:8766/api/cursor/stream');
    sockets[0].sample(.9,.2);
    assert.deepEqual(viewer.target,{x:.9,y:.2},'stream samples must reach the renderer immediately');
    finishOldRead();await new Promise(resolve=>setTimeout(resolve,30));
    assert.deepEqual(viewer.target,{x:.9,y:.2},'a delayed RPC cannot move the eyes backwards');
    listeners.get('pointermove')({screenX:480,screenY:270,pointerType:'mouse'});
    assert.deepEqual(viewer.target,{x:-.5,y:-.5},'in-window cursor movement bypasses transport latency');
    sockets[0].sample(1,1);
    assert.deepEqual(viewer.target,{x:-.5,y:-.5},'a buffered stream packet cannot overwrite a direct pointer sample');
    window.screen.isExtended=true;
    listeners.get('pointermove')({screenX:1920,screenY:1080,pointerType:'mouse'});
    assert.deepEqual(viewer.target,{x:-.5,y:-.5},'multiple monitors retain native virtual-desktop coordinates');
    tracker.stop();assert.equal(listeners.size,0,'all direct-pointer listeners are removed when disabled');
    assert.equal(sockets[0].closed,true);
    sockets[0].sample(-.8,-.8);assert.equal(viewer.target,null,'late messages after stop must be ignored');
    tracker.start();sockets[1].sample(.5,.7);
    sockets[0].sample(-1,-1);assert.deepEqual(viewer.target,{x:.5,y:.7},'a previous session cannot overwrite the new gaze');
    tracker.stop();
    console.log('PASS: cursor streaming bypasses repeated RPC, rejects stale replies, and closes cleanly');
})().catch(error=>{tracker.stop();console.error(error);process.exitCode=1;});
