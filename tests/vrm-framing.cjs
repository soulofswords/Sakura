const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),THREE=require('../static/vendor/three/build/three.cjs');
const ctx={THREE,window:{}};
vm.runInNewContext(fs.readFileSync('static/js/model-viewer.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export default class ModelViewer','class ModelViewer')+'\nthis.Viewer=ModelViewer;',ctx);
for(const scale of [1,20])for(const aspect of [.6,1.8]){
 const v=Object.create(ctx.Viewer.prototype),root=new THREE.Group(),head=new THREE.Bone();head.position.y=1.65*scale;root.add(head);
 const bounds=new THREE.Box3(new THREE.Vector3(-.5*scale,0,-.15*scale),new THREE.Vector3(.5*scale,1.8*scale,.15*scale));
 Object.assign(v,{vrm:{humanoid:{getRawBoneNode(){return head;}}},animationBones:{},camera:new THREE.PerspectiveCamera(40,aspect,.01,1000),controls:{target:new THREE.Vector3(),update(){}},_visibleModelBounds(){return bounds;},fullModelView:true});
 v._autoFrame(root);const fullDistance=v.camera.position.z,fullTarget=v.controls.target.y;
 v.fullModelView=false;v._autoFrame(root);assert.ok(v.camera.position.z<fullDistance*.8,'Portrait moves closer for small and stage-scaled VRM');assert.ok(v.controls.target.y>fullTarget,'Portrait targets the upper body');assert.ok(v.camera.position.toArray().every(Number.isFinite));
 v.fullModelView=true;v._autoFrame(root);assert.equal(v.camera.position.z,fullDistance,'Switching back restores full framing');
 v.fullModelView=false;v.desktopMode=true;v._autoFrame(root);assert.equal(v.controls.target.y,fullTarget,'Desktop still frames the whole avatar');
 v.desktopMode=false;v.vrm.humanoid.getRawBoneNode=()=>null;v._autoFrame(root);assert.equal(v.camera.position.z,fullDistance,'Missing head safely falls back to full view');
}
console.log('PASS: VRM full/portrait switching, multiple scales/aspects, desktop mode and missing-head fallback');
