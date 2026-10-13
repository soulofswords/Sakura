const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync('static/js/model-viewer.js', 'utf8').replace(/\r\n/g, '\n');
const body = source.match(/_validatePmxHumanoid\(root\) \{([\s\S]*?)\n    \}\n\n    _indexVrmExpressions/);
assert.ok(body, 'PMX humanoid validator exists');
const validate = new Function('root', body[1]);
function fixture(names) {
    const rig = {isSkinnedMesh:true,geometry:{userData:{MMD:{bones:names.map(name=>({name}))}}}};
    return {traverse(callback){callback(rig);}};
}
for (const names of [
    ['センター','上半身','頭','左腕','右腕','左足','右足'],
    ['髋骨','上身','头','左上臂','右上臂','左大腿','右大腿'],
    ['mixamorig:Hips','mixamorig:Spine','mixamorig:Head','mixamorig:LeftArm','mixamorig:RightArm','mixamorig:LeftLeg','mixamorig:RightLeg'],
]) assert.doesNotThrow(()=>validate(fixture(names)));
assert.throws(()=>validate(fixture(['root','head','tail'])),/humanoid skeleton.*left arm/i);
console.log('PASS: PMX humanoid detection accepts Japanese, Chinese and English rigs and reports non-humanoid skeletons');
