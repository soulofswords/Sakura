const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const context={};vm.runInNewContext(fs.readFileSync('static/js/tracking-distance.js','utf8'),context);const D=context.TrackingDistance;
const face=Array.from({length:478},(_,i)=>({x:.48+(i%9)*.004,y:.2+(i%11)*.004,z:-.01}));
for(const aspect of [4/3,16/9,9/16]){
 const roi=D.faceRegion(face,null,aspect);assert.ok(roi&&roi.width<.3);assert.ok(Math.abs(roi.height/roi.width-aspect)<1e-6);
 for(const p of face)assert.ok(p.x>=roi.x&&p.x<=roi.x+roi.width&&p.y>=roi.y&&p.y<=roi.y+roi.height);
 const result=D.remap([{x:.5,y:.5,z:-.1}],roi)[0];assert.ok(Math.abs(result.x-(roi.x+.5*roi.width))<1e-6);assert.equal(result.z,-.1*roi.width);
}
const pose=Array.from({length:33},(_,i)=>({x:i%2?.46:.54,y:i<11?.2:i<13?.3:.5,visibility:.9}));
assert.ok(D.faceRegion([],pose,16/9));assert.ok(D.handRegion(pose,16/9));pose[15].visibility=.2;assert.equal(D.handRegion(pose,16/9),null,'No wrist hallucination');
assert.equal(D.faceRegion([],[],16/9),null);assert.equal(D.box([{x:NaN,y:.2}],16/9),null);
for(const center of [0,.99]){const roi=D.box([{x:center,y:center},{x:Math.min(1,center+.01),y:Math.min(1,center+.02)}],16/9);assert.ok(roi.x>=0&&roi.y>=0&&roi.x+roi.width<=1.00001&&roi.y+roi.height<=1.00001);}
console.log('PASS: small-face zoom, aspect-preserving ROI, pose-guided reacquisition, distant-hand crop, original-frame remapping and absent-wrist rejection');
