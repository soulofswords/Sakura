// Background asset audit: parses files, exercises the production material policy,
// and reports risks. It does not launch a viewer or change imported model files.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..');process.chdir(root);
const source=fs.readFileSync('static/js/model-viewer.js','utf8').replace(/\r\n/g,'\n');
const prepare=new Function('THREE','root',source.match(/_preparePmxMaterials\(root\) \{([\s\S]*?)\n    \}\n\n    _fixPairedSurfaceMaterials/)[1]);
const c=vm.createContext({console,TextDecoder});
vm.runInContext(fs.readFileSync('static/vendor/three/examples/jsm/libs/mmdparser.module.js','utf8').replace('export { MMDParser, CharsetEncoder, Parser };','globalThis.Parser=Parser;'),c);
function files(dir) {return fs.readdirSync(dir,{withFileTypes:true}).filter(e=>e.name!=='__MACOSX' && !e.name.startsWith('._')).flatMap(e=>e.isDirectory()?files(path.join(dir,e.name)):[path.join(dir,e.name)]);}
function color(values) {return {r:values[0],g:values[1],b:values[2],setRGB(r,g,b){Object.assign(this,{r,g,b});}};}
const report={generated:new Date().toISOString(),scope:'All PMX assets: parse, material policy, normal validation. Not a visual render certification.',models:[]};
for(const file of files('models').filter(f=>/\.pmx$/i.test(f))) {
 const item={file:file.split(path.sep).join('/')};
 try {
  const b=fs.readFileSync(file);const data=new c.Parser().parsePmx(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),true);
  const materials=data.materials.map(m=>({name:m.name,isMMDToonMaterial:true,opacity:m.diffuse[3],diffuse:color(m.diffuse),emissive:color(m.ambient.map(v=>v*.2)),
   map:m.textureIndex>=0?{name:data.textures[m.textureIndex]}:null,
   gradientMap:m.toonIndex>=0?{name:m.toonFlag===0?data.textures[m.toonIndex]:`shared-toon-${m.toonIndex}`} : null,
   userData:{MMD:{mapFileName:data.textures[m.textureIndex]}},fragmentShader:'outgoingLight += matcapColor.rgb;'}));
  const ramps=materials.map(m=>m.gradientMap);
  prepare.call({}, {NormalBlending:1}, {traverse(fn){fn({material:materials});}});
  item.materials=materials.length;
  item.authoredSkinRampsPreserved=materials.filter((m,i)=>ramps[i] && m.gradientMap===ramps[i] && /(?:脸|顔|颜|肌|皮肤|\bskin\b|(?:^|_)face(?:$|_)|(?:^|_)body(?:$|_))/iu.test(m.name)).map(m=>m.name);
  item.targetedRampOverrides=materials.filter((m,i)=>ramps[i] && m.gradientMap!==ramps[i]).map(m=>m.name);
  item.invalidNormals=data.vertices.filter(v=>!v.normal.every(Number.isFinite)||Math.hypot(...v.normal)<1e-6).length;
  item.textures=data.textures;
  item.diffuseIndices=[...new Set(data.materials.map(m=>m.textureIndex).filter(i=>i>=0))];
  item.sphereIndices=[...new Set(data.materials.filter(m=>m.envFlag).map(m=>m.envTextureIndex).filter(i=>i>=0))];
  item.status='parsed';
 }catch(error){item.status='error';item.error=error.message;}
 report.models.push(item);
}
fs.mkdirSync('audit-results',{recursive:true});
fs.writeFileSync('audit-results/pmx-shading-library.json',JSON.stringify(report,null,2));
console.log(JSON.stringify({models:report.models.length,parsed:report.models.filter(m=>m.status==='parsed').length,errors:report.models.filter(m=>m.status==='error').length,
 modelsWithPreservedSkinRamps:report.models.filter(m=>m.authoredSkinRampsPreserved?.length).length,modelsWithInvalidNormals:report.models.filter(m=>m.invalidNormals).length}));
