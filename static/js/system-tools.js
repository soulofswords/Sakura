export function installSystemTools(){
 const box=document.getElementById('system-tools'),status=document.getElementById('system-tools-status');
 if(!box)return;
 const evidenceInput=document.getElementById('evidence-threshold');
 if(evidenceInput){
  fetch('/api/settings').then(r=>r.json()).then(data=>{evidenceInput.value=data.evidence_confidence_threshold??.9;}).catch(()=>{});
  evidenceInput.onchange=async()=>{const value=Number(evidenceInput.value);if(!Number.isFinite(value)||value<0||value>1)return;evidenceInput.disabled=true;try{const response=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({evidence_confidence_threshold:value})});if(!response.ok)throw new Error('Could not save evidence threshold.');status.textContent='Evidence threshold saved.';}catch(error){status.textContent=error.message;}finally{evidenceInput.disabled=false;}};
 }
 const memoryToggle=document.getElementById('long-term-memory-toggle'),memoryStatus=document.getElementById('long-term-memory-status');
 const describeMemory=data=>{
  if(!data||!data.enabled){memoryStatus.textContent=(data&&data.note)||'Off: facts are forgotten when this app closes.';return;}
  const megabytes=v=>(v/1024**2).toFixed(1)+' MB';
  memoryStatus.textContent='On: '+(data.live_count??data.memories)+' active fact(s), '+data.memories+' total ledger records of '+data.limit+' kept on this PC in '+megabytes(data.database_bytes||0)+
   '. Lookups use '+data.embedder+(data.semantic_retrieval?'':' (word overlap only: no local meaning model found)')+
   '. Clear memory (🧹) deletes them.';
 };
 if(memoryToggle&&memoryStatus){
  const refreshMemory=()=>fetch('/api/long-term-memory').then(r=>r.json()).then(describeMemory).catch(()=>{});
  fetch('/api/settings').then(r=>r.json()).then(data=>{memoryToggle.checked=!!data.long_term_memory;}).then(refreshMemory).catch(()=>{});
  memoryToggle.onchange=async()=>{const desired=memoryToggle.checked;memoryToggle.disabled=true;try{const response=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({long_term_memory:desired})});if(!response.ok)throw Error('Could not save that.');const data=await response.json();memoryToggle.checked=!!(data.settings&&data.settings.long_term_memory);describeMemory(data.long_term_memory);}catch(error){memoryToggle.checked=!desired;memoryStatus.textContent=error.message;}finally{memoryToggle.disabled=false;}};
 }
 const checks={computer_control_enabled:document.getElementById('system-tools-permission'),phone_system_access_enabled:document.getElementById('phone-system-access'),phone_clipboard_enabled:document.getElementById('phone-clipboard-access')};
 const paceToggle=document.getElementById('relationship-adaptation-toggle'),paceStatus=document.getElementById('relationship-status');
 const describePace=data=>{
  if(!data)return;
  if(!data.enabled){paceStatus.textContent=(data.note||'Off: replies do not use conversation pacing state.')+' Nothing is deleted; the numbers simply stop being used.';return;}
  paceStatus.textContent=data.stage_label+': '+data.turns+' messages over '+data.days_known+' days in '+data.sessions+' sittings. '
   +'Tone signal '+(data.warmth>0.15?'friendly':data.warmth<-0.15?'curt':'neutral')+', boundary signal '+(data.boundary>=0.45?'active':'none')+
   '. Derived from counts and tone words on this PC; no message text is stored.';
 };
 if(paceToggle&&paceStatus){
  const refreshPace=()=>fetch('/api/relationship').then(r=>r.json()).then(describePace).catch(()=>{});
  fetch('/api/settings').then(r=>r.json()).then(data=>{paceToggle.checked=data.relationship_adaptation!==false;}).then(refreshPace).catch(()=>{});
  paceToggle.onchange=async()=>{const desired=paceToggle.checked;paceToggle.disabled=true;try{const response=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({relationship_adaptation:desired})});if(!response.ok)throw Error('Could not save that.');const data=await response.json();paceToggle.checked=!!(data.settings&&data.settings.relationship_adaptation);describePace(data.relationship_adaptation);}catch(error){paceToggle.checked=!desired;paceStatus.textContent=error.message;}finally{paceToggle.disabled=false;}};
 }
 let busy=false;
 const request=async(path,body)=>{const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw Error(data.error||'PC tool failed');return data;};
 fetch('/api/settings').then(r=>r.json()).then(data=>{for(const [key,input]of Object.entries(checks))input.checked=!!data[key];}).catch(()=>{});
 for(const [key,input]of Object.entries(checks))input.onchange=async()=>{const desired=input.checked;input.disabled=true;try{await request('/api/settings',{[key]:desired});if(key==='computer_control_enabled'){const other=document.getElementById('computer-control-toggle');if(other)other.checked=desired;}status.textContent=desired?'Permission enabled. Paired phones can request this tool.':'Permission disabled.';}catch(error){input.checked=!desired;status.textContent=error.message;}finally{input.disabled=false;}};
 const personaPicker=document.getElementById('persona-picker'),personaStatus=document.getElementById('persona-status'),
  personaFile=document.getElementById('persona-card-file'),personaImport=document.getElementById('persona-card-import'),
  personaExport=document.getElementById('persona-card-export'),personaRemove=document.getElementById('persona-card-remove');
 if(personaPicker&&personaStatus&&personaFile){
  const cardsOf=data=>(data.items||[]).filter(item=>item.kind==='card');
  const describe=data=>{
   const active=(data.items||[]).find(item=>item.active)||{};
   personaStatus.textContent=(active.kind==='card'
     ?'Speaking as '+active.name+': its sheet adds '+data.overlay_characters+' characters to the prompt.'
     :'Speaking as the shipped persona; no imported card is in the prompt.')+
    ' '+cardsOf(data).length+' card(s) of '+data.limit+' kept on this PC. '+data.note;
   const selected=(data.items||[]).find(item=>item.id===personaPicker.value)||{};
   personaExport.disabled=personaRemove.disabled=selected.kind!=='card';
  };
  const render=async()=>{
   const data=await request('/api/personas');
   personaPicker.replaceChildren();
   for(const item of data.items||[]){const option=document.createElement('option');option.value=item.id;
    option.textContent=item.kind==='card'?item.name+' · imported card':item.name+' · shipped persona';personaPicker.append(option);}
   personaPicker.value=data.active;
   describe(data);
   return data;
  };
  const fail=error=>{personaStatus.textContent=error.message;};
  render().catch(()=>{});
  personaPicker.onchange=async()=>{const chosen=personaPicker.value;try{await request('/api/personas/activate',{persona_id:chosen});await render();}catch(error){personaPicker.value=chosen;fail(error);}};
  personaImport.onclick=()=>personaFile.click();
  personaFile.onchange=async()=>{
   const file=personaFile.files&&personaFile.files[0];
   personaFile.value='';
   if(!file)return;
   if(file.size>12*1024*1024){personaStatus.textContent='That file is over the 12 MB card limit.';return;}
   personaImport.disabled=true;
   try{
    const url=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});
    const data=await request('/api/personas/import',{file_name:file.name,data:String(url).split(',')[1]||''});
    personaStatus.textContent='Imported '+data.name+'. '+
     (data.dropped&&data.dropped.length?'Its '+data.dropped.join(', ')+' field(s) were left out. ':'')+
     (data.truncated&&data.truncated.length?'Over-long parts were cut: '+data.truncated.join(', ')+'. ':'')+
     'Choose it in the Character role list to use it.';
    await render();
   }catch(error){fail(error);}finally{personaImport.disabled=false;}
  };
  personaExport.onclick=async()=>{try{const data=await request('/api/personas/export',{persona_id:personaPicker.value});
   personaStatus.textContent='Saved a V2 JSON card at '+data.path+' ('+data.bytes+' bytes).';}catch(error){fail(error);}};
  personaRemove.onclick=async()=>{const chosen=personaPicker.value;
   if(!confirm('Forget this imported card from this PC? The original file is untouched.'))return;
   try{await request('/api/personas/delete',{persona_id:chosen});await render();}catch(error){fail(error);}};
 }
 async function refresh(){
  if(busy)return;busy=true;
  try{
   const data=await request('/api/assistant-tools/status');
   const gib=v=>(v/1024**3).toFixed(1)+' GB';
   document.getElementById('system-tools-metrics').textContent=[data.cpu_percent===undefined?'CPU: sampling…':'CPU: '+data.cpu_percent+'%',data.ram?'RAM: '+gib(data.ram.used_bytes)+' / '+gib(data.ram.total_bytes)+' ('+data.ram.percent+'%)':'',...(data.gpus||[]).map(g=>g.name+': '+(g.utilization_percent===null?'usage unavailable':g.utilization_percent+'%')+(g.vram_total_bytes&&g.vram_used_bytes!==null?' · VRAM '+gib(g.vram_used_bytes)+' / '+gib(g.vram_total_bytes)+' ('+g.vram_percent+'%)':g.vram_total_bytes?' · VRAM used unavailable / '+gib(g.vram_total_bytes):' · dedicated VRAM unavailable')),data.battery?'Battery: '+(data.battery.percent??'unknown')+'%':'','System drive free: '+gib(data.disk.free_bytes)].filter(Boolean).join(' · ');
   status.textContent='Updated '+new Date(data.sampled_at*1000).toLocaleTimeString();
  }catch(error){status.textContent=error.message;}finally{busy=false;}
 }
 document.getElementById('system-tools-refresh').onclick=refresh;
 for(const button of box.querySelectorAll('[data-volume-action]'))button.onclick=async()=>{button.disabled=true;try{const operation=button.dataset.volumeAction;const data=await request('/api/assistant-tools/device',{action:'audio.volume',operation,value:Number(document.getElementById('system-tools-volume').value)});status.textContent=data.reply;}catch(error){status.textContent=error.message;}finally{button.disabled=false;}};
 document.getElementById('system-tools-capabilities').onclick=async()=>{try{const data=await request('/api/assistant-tools/capabilities');document.getElementById('system-tools-list').textContent=data.capabilities.map(x=>x.name+': '+x.examples.join('; ')).join('\n');}catch(error){status.textContent=error.message;}};
 document.getElementById('system-tools-results').onclick=async()=>{try{const data=await request('/api/assistant-tools/runs');document.getElementById('system-tools-list').textContent=data.runs.slice(-5).map(r=>r.status+': '+r.steps.map(s=>(s.ok?'✓ ':'✗ ')+s.request+' — '+s.reply).join(' | ')).join('\n')||'No action sequences in this app session.';}catch(error){status.textContent=error.message;}};
 document.getElementById('system-tools-cancel').onclick=async()=>{try{const data=await request('/api/assistant-tools/cancel',{});status.textContent=data.cancelled?'Stopping before the next action.':'No action sequence is running.';}catch(error){status.textContent=error.message;}};
 const timer=setInterval(()=>{if(!document.hidden&&box.getClientRects().length)void refresh();},3000);
 window.addEventListener('pagehide',()=>clearInterval(timer));
}
