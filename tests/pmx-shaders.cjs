const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync('static/js/model-viewer.js', 'utf8').replace(/\r\n/g,'\n');
const sanitize = new Function('root', source.match(/_sanitizeGeometry\(root\) \{([\s\S]*?)\n    \}/)[1]);
const retained = [{count:0}];
const meshes = [
 {geometry:{morphAttributes:{position:[],normal:[],color:[]}}},
 {geometry:{morphAttributes:{position:retained}}}
];
sanitize({traverse(fn){meshes.forEach(fn)}});
assert.deepEqual(meshes[0].geometry.morphAttributes,{});
assert.equal(meshes[1].geometry.morphAttributes.position,retained);
const check = new Function('root',source.match(/_checkModelShaders\(root\) \{([\s\S]*?)\n    \}\n\n    async _loadVrm/)[1]);
let linked = false;
const viewer={renderer:{getContext(){return {LINK_STATUS:1,getProgramParameter(){return linked},getProgramInfoLog(){return 'test compile failure'}}},properties:{get(){return {currentProgram:{program:{}}}}}}};
const root={traverse(fn){fn({material:[{name:'Mask00'},{name:'Mask02'}]})}};
const originalError=console.error;console.error=()=>{};
try {assert.throws(()=>check.call(viewer,root),/Mask00/);} finally {console.error=originalError;}
linked=true;assert.doesNotThrow(()=>check.call(viewer,root));
console.log('PASS: empty morph lists removed, real morphs preserved, failed shader rejected before display');
