const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const s=fs.readFileSync('static/js/model-viewer.js','utf8').replace(/\r\n/g,'\n');
const validate=new Function('data',s.match(/_validatePmxReferences\(data\) \{([\s\S]*?)\n    \}\n\n    _preparePmxMorphData/)[1]);
const c=vm.createContext({console,TextDecoder});vm.runInContext(fs.readFileSync('static/vendor/three/examples/jsm/libs/mmdparser.module.js','utf8').replace('export { MMDParser, CharsetEncoder, Parser };','globalThis.P=Parser;'),c);
for(const file of ['models/pmx/Miku universe/Haku/Tda Haku Crazy/Tda Haku Crazy Black.pmx','models/pmx/Miku universe/Haku/Tda Haku Crazy/Tda Haku Crazy White.pmx','models/pmx/anime/Livbbies/Parlor Dragonmaid/Parla.pmx']) {
 const b=fs.readFileSync(file),data=new c.P().parsePmx(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),true),fixed=validate(data);
 for(const m of fixed.morphs){if(m.type===0)assert.ok(m.elements.every(e=>fixed.morphs[e.index]));if(m.type===8)assert.ok(m.elements.every(e=>e.index===-1||data.materials[e.index]));}
 console.log('PASS: invalid group/material references removed:',file);
}
const material={isMMDToonMaterial:true,map:{},fragmentShader:'outgoingLight += matcapColor.rgb;',transparent:true};
const prepare=new Function('THREE','root',s.match(/_preparePmxMaterials\(root\) \{([\s\S]*?)\n    \}\n\n    _fixPairedSurfaceMaterials/)[1]);
const authored={isMMDToonMaterial:true,name:'skin',map:{},emissiveMap:null,fragmentShader:'outgoingLight += matcapColor.rgb;',opacity:1,transparent:false};
prepare.call({pmxReferenceMode:true},{NormalBlending:1},{traverse(fn){fn({material:authored})}});
assert.equal(authored.emissiveMap,authored.map);
assert.equal(authored.fragmentShader,'outgoingLight += matcapColor.rgb;');
prepare({NormalBlending:1},{traverse(fn){fn({material})}});assert.equal(material.emissiveMap,material.map);assert.ok(material.fragmentShader.includes('* 0.12'));assert.equal(material.blending,1);
console.log('PASS: textured ambient, bounded shine, standard alpha blending');
const eyeOverlay={isMMDToonMaterial:true,map:{transparent:true},opacity:1,fragmentShader:'outgoingLight += matcapColor.rgb;',transparent:false};
prepare({NormalBlending:1},{traverse(fn){fn({material:eyeOverlay})}});
assert.equal(eyeOverlay.transparent,true);
assert.equal(eyeOverlay.depthWrite,true);
assert.equal(eyeOverlay.alphaTest,0.01);
console.log('PASS: decoded eye overlay alpha propagated to material');
const translucent={isMMDToonMaterial:true,map:{transparent:true},opacity:.5,fragmentShader:'outgoingLight += matcapColor.rgb;',transparent:true};
prepare({NormalBlending:1},{traverse(fn){fn({material:translucent})}});
assert.equal(translucent.depthWrite,false,'Authored translucent surfaces still blend without writing depth');
for (const reference of [false,true]) {
 const face={isMMDToonMaterial:true,name:'颜',map:{transparent:false},opacity:1,transparent:true,
  fragmentShader:'outgoingLight += matcapColor.rgb;'};
 prepare.call({pmxReferenceMode:reference},{NormalBlending:1},{traverse(fn){fn({material:face});}});
 assert.equal(face.depthWrite,true,'Full-opacity alpha-morph face occludes hidden expression cards, also in reference mode');
}
console.log('PASS: full-opacity morph materials retain occlusion; translucent surfaces still blend');
const fringe={isMMDToonMaterial:true,name:'f头发3',map:{transparent:true},opacity:1,transparent:true,
    userData:{MMD:{mapFileName:'taffy_hair_color.png'}},fragmentShader:'outgoingLight += matcapColor.rgb;'};
prepare({NormalBlending:1},{traverse(fn){fn({material:fringe})}});
assert.equal(fringe.transparent,false);assert.equal(fringe.alphaTest,.2);assert.equal(fringe.depthWrite,true);
const unrelatedHair={...fringe,userData:{MMD:{mapFileName:'another_hair.png'}},transparent:true,alphaTest:.01};
prepare({NormalBlending:1},{traverse(fn){fn({material:unrelatedHair})}});
assert.equal(unrelatedHair.transparent,true,'Other hair atlases retain their alpha behavior');
const preservedHair={...fringe,transparent:true,alphaTest:.01};
prepare.call({pmxReferenceMode:true},{NormalBlending:1},{traverse(fn){fn({material:preservedHair})}});
assert.equal(preservedHair.transparent,false,'Reference/fallback loading must also retain opaque Taffy bangs');
assert.equal(preservedHair.alphaTest,.2);assert.equal(preservedHair.depthWrite,true);
const translucentTaffy={...fringe,opacity:.5,transparent:true};
prepare.call({pmxReferenceMode:true},{NormalBlending:1},{traverse(fn){fn({material:translucentTaffy})}});
assert.equal(translucentTaffy.transparent,true,'Authored translucent Taffy surfaces remain translucent');
console.log('PASS: Taffy opaque strand cutouts; other models and authored translucency preserved, including reference/fallback loads');
function skinMaterial(name, file) {
 return {name,isMMDToonMaterial:true,map:{},opacity:1,gradientMap:{},
  userData:{MMD:{mapFileName:file}},fragmentShader:'outgoingLight += matcapColor.rgb;',
  emissive:{r:.2,g:.2,b:.2,setRGB(r,g,b){Object.assign(this,{r,g,b});}}};
}
const princessBody=skinMaterial('body','tga\\body00_MikuAp_b.tga');
const princessFace=skinMaterial('face01','tga\\face_MikuAp_b fixed.png');
const princess={traverse(fn){fn({material:[princessBody,princessFace,
 skinMaterial('body03','tga\\body02_MikuAp.tga'),{name:'Clothes - Top Crystal'}]});}};
prepare({NormalBlending:1},princess);
assert.notEqual(princessBody.gradientMap,null);
assert.notEqual(princessFace.gradientMap,null);
assert.equal(princessBody.emissive.r,.2);
assert.equal(princessFace.emissive.r,.2);
const unrelated=skinMaterial('body03','tga\\body02_MikuAp.tga');
prepare({NormalBlending:1},{traverse(fn){fn({material:unrelated});}});
assert.notEqual(unrelated.gradientMap,null,'Princess correction is scoped to its material profile');
assert.equal(unrelated.emissive.r,.06);
console.log('PASS: Princess authored ramp and ambient preserved; other profiles unchanged');

const shenheFace=skinMaterial('颜','tex/颜.png');
const shenheBody=skinMaterial('肌','tex/肌.png');
const shenheShoulder=skinMaterial('肌2','tex/体.png');
prepare({NormalBlending:1},{traverse(fn){fn({material:[shenheFace,shenheBody,shenheShoulder,
 {name:'髪spa+'},{name:'神之眼AL'}]});}});
assert.equal(shenheShoulder.emissive.r,shenheFace.emissive.r,'Numbered shoulder skin gets the same fill as the face');
assert.equal(shenheBody.emissive.r,shenheFace.emissive.r);
assert.notEqual(shenheShoulder.gradientMap,null,'Authored shoulder shading ramp is preserved');
const unrelatedShoulder=skinMaterial('肌2','different.png');
prepare({NormalBlending:1},{traverse(fn){fn({material:unrelatedShoulder});}});
assert.equal(unrelatedShoulder.emissive.r,.06,'Other model lighting is not changed by the Shenhe profile');
console.log('PASS: Shenhe shoulder, body and face share a neutral skin fill');

for (const name of ['肌','肌2','颜','skin','face','body','皮肤','Body.001']) {
 const skin=skinMaterial(name,'skin.png');
 const authoredRamp=skin.gradientMap;
 prepare({NormalBlending:1},{traverse(fn){fn({material:skin});}});
 assert.equal(skin.gradientMap,authoredRamp,`${name}: keep authored ramp instead of hard default bands`);
}
console.log('PASS: multilingual skin and face materials retain authored shading ramps');
const nanallyHair=skinMaterial('前发','tex\\player_010_nanally_hair_01_d.TGA');
const nanallyFace=skinMaterial('脸','tex\\T_player_010_nanally_face_d.TGA');
const originalRamp=nanallyHair.gradientMap;
for (const m of [nanallyHair,nanallyFace]) m.emissive.multiplyScalar=function(f){this.r*=f;this.g*=f;this.b*=f;};
prepare({NormalBlending:1},{traverse(fn){fn({material:[nanallyHair,nanallyFace]});}});
assert.equal(nanallyHair.emissive.r,1,'Nanally authored ambient attenuation reversed');
assert.equal(nanallyFace.emissive.r,1);
prepare({NormalBlending:1},{traverse(fn){fn({material:[nanallyHair,nanallyFace]});}});
assert.equal(nanallyHair.emissive.r,1,'Repeated preparation must not compound ambient');
assert.equal(nanallyHair.gradientMap,originalRamp);
assert.equal(nanallyHair.emissiveMap,nanallyHair.map);
assert.equal(unrelated.emissiveIntensity,undefined,'Other model lighting unaffected');
console.log('PASS: Nanally authored ambient restored without changing texture, toon or other profiles');
