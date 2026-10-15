const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context={};vm.runInNewContext(fs.readFileSync('static/js/live2d-controls.js','utf8').replace('export function','function')+'\nthis.install=installLive2DControls;',context);
const handlers={},view={style:{},addEventListener:(type,fn)=>handlers[type]=fn,setPointerCapture(){},getBoundingClientRect:()=>({left:0,top:0,width:400,height:400})};
const owner={camera:{zoom:1},setDisplaySize(value){this.camera.zoom=Math.max(.4,value/100);}},layer={pan:{x:0,y:0},fits:0,fit(){this.fits++;}};
context.install(view,owner,layer);
function event(type,id,x,y,button=0){handlers[type]({pointerId:id,clientX:x,clientY:y,button,cancelable:true,preventDefault(){}});}
assert.equal(view.style.touchAction,'none');
event('pointerdown',1,100,200);event('pointerdown',2,300,200);event('pointermove',1,50,200);event('pointermove',2,350,200);
assert.ok(Math.abs(owner.camera.zoom-1.5)<1e-10,'Spreading two fingers zooms in');
assert.ok(Math.abs(layer.pan.x)<1e-10,'Pinch center stays fixed');
event('pointermove',1,100,200);event('pointermove',2,300,200);assert.ok(Math.abs(owner.camera.zoom-1)<1e-10,'Bringing fingers together zooms out');
event('pointerup',2,300,200);const pan=layer.pan.x;event('pointermove',1,120,210);assert.equal(layer.pan.x,pan+20,'One remaining finger resumes dragging without a jump');
event('pointercancel',1,120,210);const stopped=layer.pan.x;event('pointermove',1,200,210);assert.equal(layer.pan.x,stopped);
event('pointerdown',3,150,150);event('pointermove',3,160,170);assert.equal(layer.pan.x,stopped+10,'Desktop left-drag is preserved');event('lostpointercapture',3,160,170);
event('pointerdown',4,20,20,2);event('pointermove',4,80,80,2);assert.equal(layer.pan.x,stopped+10,'Right button does not start pan');
assert.ok(layer.fits>0);console.log('PASS: Live2D two-finger zoom, pinch anchoring, one-finger pan, cancellation and mouse controls');
