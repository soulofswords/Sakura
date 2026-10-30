const assert=require('node:assert/strict'), fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/js/model-viewer.js','utf8').replace(/\r\n/g,'\n');
const prepare=new Function('data',source.match(/_preparePmxMorphData\(data\) \{([\s\S]*?)\n    \}\n\n    _sanitizeGeometry/)[1]);
const viewer={renderer:{capabilities:{maxTextureSize:4096}}};
const context=vm.createContext({console,TextDecoder});
vm.runInContext(fs.readFileSync('static/vendor/three/examples/jsm/libs/mmdparser.module.js','utf8').replace('export { MMDParser, CharsetEncoder, Parser };','globalThis.P=Parser;'),context);
const path='models/pmx/anime/Marin kitagawa/Kitagawa Marin (My DressUp Darling)/Kitagawa Marin.pmx';
const bytes=fs.readFileSync(path);const data=new context.P().parsePmx(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),true);
const reduced=prepare.call(viewer,data);
assert.equal(data.morphs.length,524);
assert.equal(reduced.morphs.length,reduced.metadata.morphCount);
for(const name of ['あ','い','う','え','お','まばたき']) assert.ok(reduced.morphs.some(m=>m.name===name && m.type===1 && m.elements.length),'Missing '+name);
const gpuBytes=Math.ceil(data.metadata.vertexCount/4096)*4096*16*reduced.morphs.length;
assert.ok(gpuBytes<=64*1024*1024);
// A group referring to a later source index must retain its weighted offsets.
const test={metadata:{format:'pmx',vertexCount:1000000,morphCount:5},morphs:[{name:'あ',type:0,elements:[{index:4,ratio:.5}]},...Array.from({length:3},()=>({name:'unused',type:2,elements:[]})),{name:'part',type:1,elements:[{index:0,position:[2,4,6]}]}]};
assert.deepEqual(prepare.call(viewer,test).morphs[0].elements[0].position,[1,2,3]);
console.log(JSON.stringify({vertices:data.metadata.vertexCount,before:data.morphs.length,after:reduced.morphs.length,gpuMorphMB:gpuBytes/1048576,kept:reduced.morphs.map(m=>m.name)}));
const animateBody=source.match(/    animate\(\) \{([\s\S]*?)\n    \}\n\n    _prepareCompanionSurface/)[1];
let disposed=0,notices=0;
const animate=new Function('requestAnimationFrame','window','CustomEvent',animateBody);
const broken={model:{},vrm:{},physics:{detach(){}},_renderFrame(){if(this.model)throw new RangeError('Array buffer allocation failed')},_disposeObject(){disposed++}};
const logError=console.error;console.error=()=>{};
try {
 for(let i=0;i<3;i++)animate.call(broken,()=>{}, {dispatchEvent(){notices++}}, class{});
} finally {console.error=logError;}
assert.equal(disposed,1);assert.equal(notices,1);assert.equal(broken.model,null);
console.log('PASS: allocation failure disposes model once and stops repeated errors');
