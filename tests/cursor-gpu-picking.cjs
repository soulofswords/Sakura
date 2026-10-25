const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const THREE=require('../static/vendor/three/build/three.cjs');
const source=fs.readFileSync('static/js/model-viewer.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export default class ModelViewer','class ModelViewer');
const context={THREE};vm.runInNewContext(source+';this.Viewer=ModelViewer;',context);
const viewer=Object.create(context.Viewer.prototype);
viewer.model=new THREE.Group();const scene=viewer.scene=new THREE.Scene();scene.add(viewer.model);
const collaborator=new THREE.Group();scene.add(collaborator);
viewer.camera=new THREE.PerspectiveCamera(40,2,.1,100);viewer.camera.position.z=5;
const background=scene.background=new THREE.Color('red');
let target={name:'main'},viewport=new THREE.Vector4(0,0,800,400),scissor=new THREE.Vector4(2,3,400,200),scissorTest=true,clearColor=new THREE.Color('blue'),clearAlpha=.4,alpha=255,renders=0;
viewer.renderer={domElement:{getBoundingClientRect:()=>({left:10,top:20,right:810,bottom:420,width:800,height:400})},outputColorSpace:THREE.SRGBColorSpace,
 getRenderTarget:()=>target,getViewport:v=>v.copy(viewport),getScissor:v=>v.copy(scissor),getScissorTest:()=>scissorTest,getClearAlpha:()=>clearAlpha,getClearColor:c=>c.copy(clearColor),
 setRenderTarget:v=>{target=v;},setViewport:(...args)=>{viewport=args[0]?.isVector4?args[0].clone():new THREE.Vector4(...args);},setScissor:v=>{scissor=v.clone();},setScissorTest:v=>{scissorTest=v;},setClearColor:(v,a)=>{clearColor.set(v);clearAlpha=a;},clear(){},
 render(s,c){renders++;assert.equal(s.background,null);assert.equal(collaborator.visible,false,'another avatar must not count as this model');assert.equal(c.view.width,1);},
 readRenderTargetPixels(t,x,y,w,h,p){assert.equal(w*h,1);p[3]=alpha;}
};
viewer._hitModelAt=()=>{throw Error('CPU skinning must never run for the drag cursor');};
assert.equal(viewer._hitModelPixelAt(410,220),true);
alpha=0;assert.equal(viewer._hitModelPixelAt(410,220),false,'transparent holes and empty pixels cannot start a drag');
assert.equal(viewer._hitModelPixelAt(0,0),false);assert.equal(renders,2,'outside the canvas must not trigger rendering');
assert.equal(scene.background,background);assert.equal(collaborator.visible,true);
assert.equal(target.name,'main');assert.deepEqual(viewport.toArray(),[0,0,800,400]);assert.deepEqual(scissor.toArray(),[2,3,400,200]);assert.equal(scissorTest,true);assert.equal(clearAlpha,.4);
viewer.renderer.render=()=>{throw Error('failed GPU pick');};assert.throws(()=>viewer._hitModelPixelAt(410,220),/failed GPU/);
assert.equal(scene.background,background);assert.equal(collaborator.visible,true);assert.equal(target.name,'main');assert.deepEqual(viewport.toArray(),[0,0,800,400]);
console.log('PASS: one-pixel GPU picking respects transparency, excludes collaborators, avoids CPU skinning, and restores renderer state on success/failure');
