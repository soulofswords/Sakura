const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let sent=[],counts={pose:0,face:0,detail:0,hands:0},closed=0;
const empty=()=>({landmarks:[],worldLandmarks:[],handedness:[]});
const landmarks=Array.from({length:478},()=>({x:.5,y:.5,z:0}));
const faceResult=()=>({faceLandmarks:[landmarks],faceBlendshapes:[{categories:[]}],facialTransformationMatrixes:[{data:new Array(16).fill(0)}]});
const context={self:{postMessage(data){sent.push(data);}},importScripts(){},performance,TrackingDistance:{faceRegion:()=>({x:.2,y:.2,width:.2,height:.2}),handRegion:()=>({x:.2,y:.2,width:.3,height:.3}),remap:p=>p}};
vm.createContext(context);vm.runInContext(fs.readFileSync('static/js/avatar-tracking-worker.js','utf8'),context);
Object.assign(context,{faceMock:{detectForVideo(){counts.face++;return faceResult();}},detailMock:{detectForVideo(){counts.detail++;return faceResult();}},poseMock:{detectForVideo(){counts.pose++;return {landmarks:[[]],worldLandmarks:[[]]};}},handsMock:{detectForVideo(){counts.hands++;return empty();}}});
vm.runInContext('face=faceMock;detailFace=detailMock;pose=poseMock;hands=handsMock;surface={width:640,height:360};context={drawImage(){}};detailSurface={};detailContext={drawImage(){}};',context);
(async()=>{
 for(let i=1;i<=6;i++)await context.self.onmessage({data:{type:'frame',image:{width:640,height:360,close(){closed++;}},timestamp:i*40,poseStride:2,inferenceWidth:640}});
 assert(!sent.some(x=>x.type==='error'),JSON.stringify(sent));
 assert.equal(counts.face,6);assert.equal(counts.pose,3);assert.equal(counts.detail,1);assert.equal(counts.hands,8);assert.equal(closed,6);
 assert(sent.every(x=>Number.isFinite(x.processingMs)));
 assert.equal(sent[0].face.matrix,null,'one isolated detection cannot animate a face');
 assert.equal(sent[1].face.matrix,null,'presence needs three consecutive camera detections');
 assert(sent[2].face.matrix,'three detections confirm presence');
 // The crop detector still reports a face, but the real full frame is empty.
 context.faceMock.detectForVideo=()=>({faceLandmarks:[],faceBlendshapes:[],facialTransformationMatrixes:[]});
 await context.self.onmessage({data:{type:'frame',image:{width:640,height:360,close(){}},timestamp:300,poseStride:2,inferenceWidth:640}});
 const absent=sent.at(-1);assert.equal(absent.face.matrix,null);assert.equal(absent.face.landmarks.length,0);assert.equal(absent.face.blendshapes.length,0);assert.equal(absent.pose,null);
 assert.equal(counts.detail,1,'crop detector cannot keep absent face alive');
 context.faceMock.detectForVideo=faceResult;
 await context.self.onmessage({data:{type:'frame',image:{width:640,height:360,close(){}},timestamp:340,poseStride:2,inferenceWidth:640}});
 assert.equal(sent.at(-1).face.matrix,null,'re-entry must confirm presence again');
 console.log('PASS: isolated/empty-camera detections rejected; crop cannot sustain phantom face or body; re-entry requires confirmation');

 context.mockTask={async createFromOptions(f,options){if(options.baseOptions.delegate==='GPU')throw Error('WebGL unsupported');return {cpu:true};}};
 vm.runInContext('preferGPU=true;fileset={};',context);
 assert.equal((await vm.runInContext("createDetector(mockTask,{baseOptions:{delegate:'CPU'}})",context)).cpu,true);
 console.log('PASS: face every frame; torso at half rate; supplemental crops at one-third rate; bitmap cleanup and mobile GPU fallback');
})().catch(e=>{console.error(e);process.exitCode=1;});
