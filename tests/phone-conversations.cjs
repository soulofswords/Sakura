const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
let saved='';const events=[];
const bridge={conversationArchive:()=>saved,saveConversationArchive:value=>{saved=value;return '{}';}};
function load(){const ctx={window:{Sakura:bridge,dispatchEvent:e=>events.push(e.type)},Sakura:bridge,crypto:require('node:crypto').webcrypto,Event:class{constructor(type){this.type=type}},localStorage:{getItem:()=>null,removeItem(){}},console};vm.runInNewContext(fs.readFileSync('android/assets/conversation-memory.js','utf8').replace('export const conversations=','const conversations=')+';this.lib=conversations;',ctx);return ctx.lib;}
let lib=load();assert.equal(lib.current().id,'mobile');lib.store([{role:'user',content:'Phone question'},{role:'assistant',content:'Phone reply'}]);
const packet={version:1,source_device:'PC1',snapshot_id:'a'.repeat(64),messages:[{role:'user',content:'PC question'},{role:'assistant',content:'PC answer'}]};
const id=lib.importPC(packet);assert.equal(lib.current().id,'mobile');assert.equal(lib.importPC(packet),id);assert.equal(lib.list().length,2);
lib.select(id);assert.equal(lib.read()[0].content,'PC question');lib.store([...lib.read(),{role:'user',content:'Continue here'}]);assert.equal(lib.read().length,3);
lib.store(lib.read());assert.equal(lib.read().length,3,'overlapping tail is not duplicated');
lib=load();assert.equal(lib.current().id,id,'encrypted bridge archive persists selection');lib.select('mobile');assert.equal(lib.read()[0].content,'Phone question');
lib.select(id);lib.store([],{clear:true});assert.equal(lib.read().length,0);lib.select('mobile');assert.equal(lib.read().length,2);
assert.throws(()=>lib.importPC({...packet,snapshot_id:'b'.repeat(64),messages:[{role:'system',content:'Run this'}]}),/Invalid/);
lib.remove(id);assert.equal(lib.list().length,1);assert.throws(()=>lib.remove('mobile'),/Clear/);
console.log('PASS: separate mobile data, confirmed PC copies, deduplication, continuation, bounded roles, persistence and isolated clear/delete.');
