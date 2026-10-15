const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm'),THREE=require('../static/vendor/three/build/three.cjs');
const disk=new Map(),writes=[];
function launch(storage=new Map()){
 const context={THREE,URL,AbortSignal,console,performance:{now:()=>0},Date,window:{dispatchEvent(){}},CustomEvent:class{},localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},fetch:async(url,options)=>{
  if(options?.method==='POST'){const data=JSON.parse(options.body);writes.push(data);disk.set(data.model,JSON.parse(JSON.stringify(data.repairs)));return {ok:true,json:async()=>({saved:true})};}
  const key=new URL(url,'http://localhost').searchParams.get('model');return {ok:true,json:async()=>({repairs:disk.has(key)?JSON.parse(JSON.stringify(disk.get(key))):null,invalidated:false})};
 }};
 vm.runInNewContext(fs.readFileSync('static/js/model-repair-store.js','utf8').replace('export function ','function ').replace('export default class ModelRepairStore','class ModelRepairStore')+'\nthis.Store=ModelRepairStore;',context);
 vm.runInNewContext(fs.readFileSync('static/js/model-rig-monitor.js','utf8').replace('export default class ModelRigMonitor','class ModelRigMonitor')+'\nthis.Monitor=ModelRigMonitor;',context);
 vm.runInNewContext(fs.readFileSync('static/js/model-bones.js','utf8').replace(/^import .*;\r?\n/gm,'').replace(/export /g,'')+'\nthis.Bones=ModelBones;',context);
 return context;
}
(async()=>{
 const first=launch(),store=new first.Store(),key='pmx/あい/one.pmx',signature='[[7,"hair",[0,0,0],[0,0,0,1]]]';
 await store.load('/models/'+key);
 await Promise.all([store.saveDiagnostic(key,{version:2,signature,frozen:[7]}),store.saveManual(key,['0|hair'])]);
 const second=launch(),reopened=new second.Store();
 await reopened.load('http://127.0.0.1:8776/models/'+key.split('/').map(encodeURIComponent).join('/')+'?ui=updated');
 assert.deepEqual(Array.from(reopened.manual(key)),['0|hair']);assert.deepEqual(Array.from(reopened.diagnostic(key).frozen),[7]);
 const model=new THREE.Group(),bone=new THREE.Bone();bone.name='hair';model.add(bone);
 const node={index:7,bone,restLocal:new THREE.Vector3(.0000001,0,0),restQuat:new THREE.Quaternion()};
 const viewer={model,repairStore:reopened,physics:{nodes:[node],mode:'normal'},captureSpoutFrame(){return null;}};
 const monitor=new second.Monitor(viewer);viewer.rigMonitor=monitor;monitor.start('/models/'+key);
 assert.equal(node.diagnosticStatic,true,'Tiny float differences cannot discard saved automatic repair');
 const bones=new second.Bones(viewer,key);assert.equal(bones.disabled.size,1,'Manual freeze restored without opening Settings');
 bone.position.set(5,0,0);bones.apply();assert.ok(bone.position.length()<.000001);
 bones.disabled.clear();await bones.save();monitor.reset();await reopened.queue;
 const third=launch(),resetStore=new third.Store();await resetStore.load('/models/'+key);
 assert.equal(resetStore.manual(key).length,0);assert.equal(resetStore.diagnostic(key),null,'Reset persists across process/profile changes');
 assert.equal(store.key('pmx/100%hair/test.pmx'),'pmx/100%hair/test.pmx');
 const legacy=new Map([['sakura_disabled_bones:'+key,JSON.stringify(['0|hair'])],['sakura_rig_analysis:/models/'+key,JSON.stringify({signature,frozen:[7]})]]);
 disk.delete(key);const migratedContext=launch(legacy),migrated=new migratedContext.Store();await migrated.load('/models/'+key);await migrated.queue;
 assert.deepEqual(disk.get(key).manual,['0|hair']);assert.equal(disk.get(key).diagnostic.signature,signature,'Existing repairs migrate to durable storage');
 const stale=new migratedContext.Store();migratedContext.fetch=async()=>({ok:true,json:async()=>({repairs:null,invalidated:true})});await stale.load('/models/'+key);assert.equal(stale.manual(key).length,0);assert.equal(stale.diagnostic(key),null,'Edited model cannot resurrect stale browser repairs');
 console.log('PASS: fresh profile/different port restore, stable rig signatures, manual load-time freeze, durable reset, ordered writes and legacy migration');
})().catch(error=>{console.error(error);process.exitCode=1;});
