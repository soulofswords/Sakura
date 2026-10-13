const fs=require('fs'),path=require('path'),vm=require('vm');
const context=vm.createContext({console,TextDecoder});vm.runInContext(fs.readFileSync('static/vendor/three/examples/jsm/libs/mmdparser.module.js','utf8').replace('export { MMDParser, CharsetEncoder, Parser };','globalThis.Parser=Parser;'),context);
function walk(folder){return fs.readdirSync(folder,{withFileTypes:true}).flatMap(item=>item.name==='__MACOSX'||item.name.startsWith('.')?[]:item.isDirectory()?walk(path.join(folder,item.name)):/\.pmx$/i.test(item.name)?[path.join(folder,item.name)]:[])}
const report=[];
for(const file of walk('models/pmx')){
 try{
 const bytes=fs.readFileSync(file);const m=new context.Parser().parsePmx(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),true);
 report.push({file,vertices:m.vertices.length,bones:m.bones.length,morphs:m.morphs.length,badVertices:m.vertices.filter(v=>v.position.some(n=>!Number.isFinite(n)||Math.abs(n)>10000)).length,badFaces:m.faces.filter(f=>f.indices.some(i=>i<0||i>=m.vertices.length)).length,textures:m.textures,materials:m.materials.map(x=>({name:x.name,diffuse:x.diffuse,ambient:x.ambient,specular:x.specular,opacity:x.diffuse[3],flag:x.flag,texture:x.textureIndex,sphere:x.envTextureIndex,sphereMode:x.envFlag,faces:x.faceCount}))});
 }catch(e){report.push({file,error:e.message})}
}
fs.writeFileSync('audit-results/library-render-audit.json',JSON.stringify(report));
console.log(JSON.stringify({models:report.length,parseFailures:report.filter(x=>x.error),geometryProblems:report.filter(x=>x.badVertices||x.badFaces).map(x=>({file:x.file,badVertices:x.badVertices,badFaces:x.badFaces}))}));
