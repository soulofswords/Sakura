const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/js/model-viewer.js','utf8').replace(/\r\n/g,'\n');
const fix=new Function('root',source.match(/_fixPmxLayeredSurfaces\(root\) \{([\s\S]*?)\n    \}\n\n    setEyeTrackingTarget/)[1]);
const c=vm.createContext({console,TextDecoder});
vm.runInContext(fs.readFileSync('static/vendor/three/examples/jsm/libs/mmdparser.module.js','utf8').replace('export { MMDParser, CharsetEncoder, Parser };','globalThis.Parser=Parser;'),c);
function load(file) {
 const b=fs.readFileSync(file);
 return new c.Parser().parsePmx(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),true);
}
function attribute(values) {
 return Object.fromEntries(['X','Y','Z','W'].map((axis,n)=>['get'+axis,i=>values[i][n]]));
}
function meshFor(data, transparentNames) {
 let start=0;
 const groups=data.materials.map((m,i)=>{const group={start,count:m.faceCount*3,materialIndex:i};start+=group.count;return group;});
 const flat=data.faces.flatMap(f=>Array.from(f.indices));
 return {material:data.materials.map(m=>({name:m.name,isMMDToonMaterial:true,opacity:m.diffuse[3],
  map:{transparent:transparentNames.includes(m.name)},depthWrite:true})),
 geometry:{groups,index:{getX:i=>flat[i]},attributes:{
  position:attribute(data.vertices.map(v=>v.position)),
  skinIndex:attribute(data.vertices.map(v=>[...v.skinIndices,0,0,0,0].slice(0,4))),
  skinWeight:attribute(data.vertices.map(v=>[...v.skinWeights,0,0,0,0].slice(0,4)))
 }}};
}
const dir='models/pmx/Azur lane/埃吉尔v1.1';
const data=load(dir+'/'+fs.readdirSync(dir).find(f=>f.endsWith('.pmx')));
const mesh=meshFor(data,['cf_m_body+']);
assert.ok(fix({traverse(fn){fn(mesh)}})>0);
const overlay=mesh.material.find(m=>m.name==='cf_m_body+');
assert.equal(overlay.depthWrite,false,'Stocking decal must not punch holes through underlying body');
assert.equal(overlay.polygonOffset,true);
assert.equal(mesh.material[0].depthWrite,true,'Base body retains depth');
// Non-overlapping sleeve textures are not changed simply for having alpha.
const sleeves=meshFor(data,['袖1','新規.001']);
fix({traverse(fn){fn(sleeves)}});
assert.equal(sleeves.material.find(m=>m.name==='袖1').polygonOffset,undefined);
console.log('PASS: real Azur Lane layered body repaired; independent sleeve surfaces preserved');
