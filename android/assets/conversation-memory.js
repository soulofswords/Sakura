/* Independent phone chats and explicitly imported PC copies. Never auto-connects. */
const initial=()=>({version:1,active_id:'mobile',threads:[{id:'mobile',origin:'mobile',title:'Mobile conversation',messages:[]}]});
function load(){try{const raw=window.Sakura?.conversationArchive?.();if(raw){const data=JSON.parse(raw);if(data.version===1&&Array.isArray(data.threads)&&data.threads.some(t=>t.id===data.active_id))return data;}}catch(_){}return initial();}
let archive=load();
function save(next){if(!window.Sakura?.saveConversationArchive)throw Error('Update Sakura Mobile to use encrypted conversation imports.');const result=JSON.parse(Sakura.saveConversationArchive(JSON.stringify(next)));if(result.error)throw Error(result.error);archive=next;window.dispatchEvent(new Event('sakura-conversation-library'));}
const active=()=>archive.threads.find(t=>t.id===archive.active_id);
export const conversations={
 supported:()=>!!window.Sakura?.saveConversationArchive,
 list:()=>archive.threads.map(({id,title,origin,messages})=>({id,title,origin,count:messages.length})),
 current:()=>({id:active().id,origin:active().origin}),
 read:()=>active().messages.slice(-20).map(row=>({...row})),
 select(id){if(!archive.threads.some(t=>t.id===id))throw Error('Conversation not found.');save({...archive,active_id:id});window.dispatchEvent(new Event('sakura-conversation-selected'));},
 store(tail,{clear=false}={}){
  const clean=tail.filter(row=>['user','assistant'].includes(row.role)&&typeof row.content==='string').map(({role,content})=>({role,content:content.slice(0,16000)}));
  const next=JSON.parse(JSON.stringify(archive)),thread=next.threads.find(t=>t.id===next.active_id);
  let overlap=0;if(!clear)for(let n=1;n<=Math.min(thread.messages.length,clean.length);n++)if(JSON.stringify(thread.messages.slice(-n))===JSON.stringify(clean.slice(0,n)))overlap=n;
  thread.messages=clear?clean:[...thread.messages,...clean.slice(overlap)].slice(-200);save(next);
 },
 importPC(packet){
  if(packet?.version!==1||!Array.isArray(packet.messages)||!packet.messages.length||packet.messages.length>200||typeof packet.source_device!=='string'||!/^[0-9a-f]{64}$/.test(packet.snapshot_id||''))throw Error('The PC returned an invalid or empty conversation.');
  if(packet.messages.some(row=>!row||!['user','assistant'].includes(row.role)||typeof row.content!=='string'||row.content.length>16000))throw Error('Invalid PC conversation messages.');
  const existing=archive.threads.find(t=>t.origin==='pc-import'&&t.source_device===packet.source_device&&t.snapshot_id===packet.snapshot_id);if(existing)return existing.id;
  if(archive.threads.length>=20)throw Error('Conversation library is full (20). Keep mobile separate or remove an unwanted copy first.');
  const id='pc-'+crypto.randomUUID(),next=JSON.parse(JSON.stringify(archive));next.threads.push({id,origin:'pc-import',title:'PC conversation '+new Date().toLocaleDateString(),source_device:packet.source_device,snapshot_id:packet.snapshot_id,messages:packet.messages.map(({role,content})=>({role,content}))});save(next);return id;
 },
 remove(id){if(id==='mobile')throw Error('Clear the mobile conversation from chat instead.');save({...archive,active_id:archive.active_id===id?'mobile':archive.active_id,threads:archive.threads.filter(t=>t.id!==id)});window.dispatchEvent(new Event('sakura-conversation-selected'));}
};
// One-time migration keeps existing phone dialogue; it never reads a PC automatically.
if(conversations.supported()&&!Sakura.conversationArchive?.()){try{const old=JSON.parse(localStorage.getItem('sakura-local-history')||'[]');conversations.store(old);localStorage.removeItem('sakura-local-history');}catch(_){}}
