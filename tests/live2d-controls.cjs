const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context={};vm.runInNewContext(fs.readFileSync('static/js/live2d-controls.js','utf8').replace('export function','function')+'\nthis.install=installLive2DControls;',context);
const handlers={},view={style:{},addEventListener:(type,fn)=>handlers[type]=fn,setPointerCapture(){},getBoundingClientRect:()=>({left:0,top:0,width:400,height:400})};
const owner={camera:{zoom:1},setDisplaySize(value){this.camera.zoom=Math.max(.4,value/100);}},layer={hitTestPoint:(x,y)=>x>=50&&x<=350&&y>=50&&y<=350,pan:{x:0,y:0},fits:0,fit(){this.fits++;}};
context.install(view,owner,layer);
function event(type,id,x,y,button=0){handlers[type]({pointerId:id,clientX:x,clientY:y,button,cancelable:true,preventDefault(){}});}
assert.equal(view.style.touchAction,'none');
event('pointermove',77,10,10);assert.equal(view.style.cursor,'default','Empty stage shows arrow');
event('pointermove',77,150,150);assert.equal(view.style.cursor,'grab','Model shows grab cursor');
event('pointerdown',77,150,150);assert.equal(view.style.cursor,'grabbing','Accepted model drag shows grabbing cursor');
event('pointerup',77,10,10);assert.equal(view.style.cursor,'default','Released drag over empty space restores arrow');

event('pointerdown',99,10,10);event('pointermove',99,100,100);assert.equal(layer.pan.x,0,'Empty canvas cannot start dragging');
event('pointerdown',1,100,200);event('pointerdown',2,300,200);event('pointermove',1,50,200);event('pointermove',2,350,200);
assert.ok(Math.abs(owner.camera.zoom-1.5)<1e-10,'Spreading two fingers zooms in');
assert.ok(Math.abs(layer.pan.x)<1e-10,'Pinch center stays fixed');
event('pointermove',1,100,200);event('pointermove',2,300,200);assert.ok(Math.abs(owner.camera.zoom-1)<1e-10,'Bringing fingers together zooms out');
event('pointerup',2,300,200);const pan=layer.pan.x;event('pointermove',1,120,210);assert.equal(layer.pan.x,pan+20,'One remaining finger resumes dragging without a jump');
event('pointercancel',1,120,210);const stopped=layer.pan.x;event('pointermove',1,200,210);assert.equal(layer.pan.x,stopped);
event('pointerdown',3,150,150);event('pointermove',3,160,170);assert.equal(layer.pan.x,stopped+10,'Desktop left-drag is preserved');event('lostpointercapture',3,160,170);
event('pointerdown',4,20,20,2);event('pointermove',4,80,80,2);assert.equal(layer.pan.x,stopped+10,'Right button does not start pan');
assert.ok(layer.fits>0);console.log('PASS: Live2D two-finger zoom, pinch anchoring, one-finger pan, cancellation and mouse controls');
