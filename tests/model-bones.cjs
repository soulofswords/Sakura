const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),THREE=require('../static/vendor/three/build/three.cjs');
const saved=new Map(),ctx={THREE,localStorage:{getItem:key=>saved.get(key),setItem:(key,value)=>saved.set(key,value)}};
vm.runInNewContext(fs.readFileSync('static/js/model-bones.js','utf8').replace(/^import .*;\r?\n/gm,'').replace(/export /g,'')+'\nthis.Bones=ModelBones;',ctx);
for(const format of ['pmx','vrm']){
    const model=new THREE.Group(),hair=new THREE.Bone();hair.name='Hair';hair.position.y=1;model.add(hair);const viewer={model,physics:{nodes:[],reset(){}}},controls=new ctx.Bones(viewer,format);
    controls.toggle('0',true);hair.rotation.z=1;controls.apply();assert.ok(Math.abs(hair.rotation.z)<1e-9);assert.ok(viewer.physics.disabledBones.has(hair));
    const reloaded=new ctx.Bones(viewer,format);assert.ok(reloaded.disabled.has('0'),'Frozen bone survives reload');reloaded.toggle('0',false);hair.rotation.z=.3;reloaded.apply();assert.equal(hair.rotation.z,.3,'Enabled bone moves');
}
console.log('PASS: PMX/VRM bone freeze, restore, physics exclusion and persistence');
