const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let frames=[],renders=0,removed=0,copies=0;
const source=fs.readFileSync('static/js/model-viewer.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export default class ModelViewer','class ModelViewer');
const context={THREE:{Loader:class{},MOUSE:{PAN:2,ROTATE:0},TOUCH:{PAN:1}},requestAnimationFrame:cb=>frames.push(cb),document:{createElement:()=>({style:{},getContext:()=>({drawImage(){copies++;}}),remove(){removed++;}})}};
vm.runInNewContext(source+'\nthis.Viewer=ModelViewer;',context);
const v=Object.create(context.Viewer.prototype);
Object.assign(v,{model:{},renderer:{domElement:{width:800,height:600}},container:{appendChild(){}},controls:{mouseButtons:{},touches:{}},_renderFrame(){renders++;},_applyTrackingRestPose(){},clearManualExpression(){},setMorph(){}});
for(const mode of ['gemini','local','vtuber']){
 v.desktopMode=false;v.setVtuberTrackingMode(mode==='vtuber');
 assert.equal(v.controls.mouseButtons.LEFT,2);assert.equal(v.controls.mouseButtons.RIGHT,0);assert.equal(v.controls.touches.ONE,1);assert.equal(v.controls.screenSpacePanning,true);
}
v._displayLoadTicket=1;v._holdPresentedFrame();assert.equal(copies,1);assert.equal(renders,1);assert.equal(v._heldFrame.width,800);
v._holdPresentedFrame();assert.equal(copies,1,'Keep original snapshot throughout rapid model changes');
const flush=()=>{while(frames.length)frames.shift()();};
v._releasePresentedFrame(1);v._displayLoadTicket=2;flush();assert.equal(removed,0,'Old load cannot uncover a new pending load');
v._displayLoading=true;v._releasePresentedFrame(2);flush();assert.equal(removed,0);
v._displayLoading=false;v._releasePresentedFrame(2);frames.shift()();assert.equal(removed,0,'Keep cover through the compositor frame');flush();assert.equal(removed,1);assert.equal(v._heldFrame,null);
console.log('PASS: all three modes share controls; presentation snapshot survives overlapping loads and releases only after ready');
