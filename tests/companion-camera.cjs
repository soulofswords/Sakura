const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
let stopped=0,captured=0,constraints;
const track={stop(){stopped++;},addEventListener(){}},stream={getTracks:()=>[track],getVideoTracks:()=>[track]};
let acquire=async c=>{constraints=c;return stream;};
const ctx={navigator:{mediaDevices:{getUserMedia:c=>acquire(c)}},document:{createElement:type=>type==='video'?{play:async()=>{},pause(){},readyState:2,videoWidth:1280,videoHeight:720}:{getContext:()=>({drawImage(){captured++;},clearRect(){}}),toDataURL:()=> 'data:image/jpeg;base64,/9j/'}}};
vm.runInNewContext(fs.readFileSync('static/js/companion-camera.js','utf8').replace('export default class','class')+'\nthis.Camera=CompanionCamera;',ctx);
(async()=>{
 const camera=new ctx.Camera();assert.equal(camera.enabled,false);assert.equal(camera.snapshot(),null);
 await camera.start('chosen');assert.equal(constraints.audio,false);assert.equal(constraints.video.deviceId.exact,'chosen');
 assert.equal(camera.snapshot(),'/9j/');assert.equal(captured,1);camera.stop();assert.equal(stopped,1);assert.equal(camera.snapshot(),null);
 let resolve;acquire=()=>new Promise(r=>resolve=r);const pending=camera.start();camera.stop();resolve(stream);await pending;
 assert.equal(camera.enabled,false);assert.equal(stopped,2,'Cancellation releases newly acquired stream');
 camera.startRemote();assert.equal(camera.enabled,true);assert.equal(camera.remote,true);assert.equal(camera.snapshot(),null);
 camera.remoteFrame('/9j/phone');assert.equal(camera.snapshot(),'/9j/phone');
 camera.stop();camera.remoteFrame('/9j/stale');assert.equal(camera.snapshot(),null);
 console.log('PASS: explicit camera enable, JPEG capture, no mic, selected device, shutdown and permission race');
})().catch(e=>{console.error(e);process.exitCode=1;});
