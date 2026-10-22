export function installSystemTools(){
 const box=document.getElementById('system-tools'),status=document.getElementById('system-tools-status');
 if(!box)return;
 const evidenceInput=document.getElementById('evidence-threshold');
 if(evidenceInput){
  fetch('/api/settings').then(r=>r.json()).then(data=>{evidenceInput.value=data.evidence_confidence_threshold??.9;}).catch(()=>{});
  evidenceInput.onchange=async()=>{const value=Number(evidenceInput.value);if(!Number.isFinite(value)||value<0||value>1)return;evidenceInput.disabled=true;try{const response=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({evidence_confidence_threshold:value})});if(!response.ok)throw new Error('Could not save evidence threshold.');status.textContent='Evidence threshold saved.';}catch(error){status.textContent=error.message;}finally{evidenceInput.disabled=false;}};
 }
 const checks={computer_control_enabled:document.getElementById('system-tools-permission'),phone_system_access_enabled:document.getElementById('phone-system-access'),phone_clipboard_enabled:document.getElementById('phone-clipboard-access')};
 let busy=false;
 const request=async(path,body)=>{const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw Error(data.error||'PC tool failed');return data;};
 fetch('/api/settings').then(r=>r.json()).then(data=>{for(const [key,input]of Object.entries(checks))input.checked=!!data[key];}).catch(()=>{});
 for(const [key,input]of Object.entries(checks))input.onchange=async()=>{const desired=input.checked;input.disabled=true;try{await request('/api/settings',{[key]:desired});if(key==='computer_control_enabled'){const other=document.getElementById('computer-control-toggle');if(other)other.checked=desired;}status.textContent=desired?'Permission enabled. Paired phones can request this tool.':'Permission disabled.';}catch(error){input.checked=!desired;status.textContent=error.message;}finally{input.disabled=false;}};
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
