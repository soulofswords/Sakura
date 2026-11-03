// Deterministic wake handling; sleeping speech never reaches a chat model.
export function wakeCommand(text,phrase='hey sakura'){
 const normalize=value=>String(value||'').toLowerCase().replace(/[,.!?।]/gu,' ').replace(/\s+/g,' ').trim();
 const raw=String(text||'').trim(),input=normalize(raw),prefixes=['wake up sakura','sakura wake up','wake up',normalize(phrase)].filter(Boolean);
 for(const prefix of prefixes)if(input===prefix||input.startsWith(prefix+' ')){
  const words=prefix.split(' ').map(word=>word.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('[\\s,.!?।]+');
  const match=new RegExp('^'+words+'(?:[\\s,.!?।]+|$)','iu').exec(raw);
  return {wake:true,command:match?raw.slice(match[0].length).trim():''};
 }
 return {wake:false,command:''};
}
