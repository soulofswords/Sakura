/* Bounded persistent memory controls; no model-written claims of a save. */
window.installAgentMemory=({api,perform,refresh})=>{
 const panel=document.createElement('section');panel.id='agent-memory';panel.className='card';panel.hidden=true;
 panel.innerHTML=`<h2>Memory & learning</h2><p>Sakura remembers verified procedures from completed Agent tasks and reuses them as guidance. Learning never approves a tool, runs an action, or trains the model weights.</p><label><input id="learning-enabled" type="checkbox"> Learn from completed tasks and use saved memory</label><label>My preferences <span class="muted">· up to 1,375 characters</span><textarea id="learning-profile" maxlength="1375" placeholder="How you want Sakura to work and communicate…"></textarea></label><label>Working notes <span class="muted">· up to 2,200 characters</span><textarea id="learning-notes" maxlength="2200" placeholder="Project conventions and useful context. Keep passwords and API keys out of memory."></textarea></label><div class="row"><button id="learning-save">Save memory settings</button><button id="learning-clear" class="reject">Forget all memory</button></div><p id="learning-status" role="status"></p><h3>Learned procedures</h3><p class="muted">Only successful tool sequences and counts are saved automatically. File contents, paths, commands, account details and full conversations are excluded. Saved notes and preferences may be sent to the AI provider you choose when planning tasks.</p><div id="learning-procedures"></div>`;
 document.querySelector('main').append(panel);const $=id=>document.getElementById(id);let dirty=false;
 for(const id of ['learning-enabled','learning-profile','learning-notes'])$(id).addEventListener('input',()=>dirty=true);
 $('learning-save').onclick=()=>perform(async()=>{await api('memory',{enabled:$('learning-enabled').checked,profile:$('learning-profile').value,notes:$('learning-notes').value});dirty=false;await refresh();$('learning-status').textContent='Memory settings saved on this PC.';});
 $('learning-clear').onclick=()=>perform(async()=>{if(!confirm('Forget all learned procedures, preferences and working notes? Existing task history and user-created skills are separate.'))return;await api('memory',undefined,'DELETE');dirty=false;await refresh();});
 return {render(data){
  if(!data)return;
  if(!dirty){$('learning-enabled').checked=data.enabled===true;$('learning-profile').value=data.profile||'';$('learning-notes').value=data.notes||'';}
  const box=$('learning-procedures');box.replaceChildren();
  if(!data.procedures?.length){const empty=document.createElement('p');empty.textContent='No procedures learned yet. Complete an Agent task with at least two successful actions.';box.append(empty);}
  for(const entry of data.procedures||[]){
   const item=document.createElement('article');item.className='connection';const title=document.createElement('h3');title.textContent=entry.category+' workflow';const steps=document.createElement('p');steps.textContent=entry.tools.join(' → ');const count=document.createElement('small');count.textContent=entry.successes+' verified completed run'+(entry.successes===1?'':'s');item.append(title,steps,count);
   const name=document.createElement('input');name.placeholder='Skill name, for example document-review';name.setAttribute('aria-label','Name for '+entry.category+' skill');name.maxLength=60;
   const row=document.createElement('div');row.className='row';const save=document.createElement('button');save.type='button';save.textContent='Save as skill';save.onclick=()=>perform(async()=>{await api('memory/'+encodeURIComponent(entry.id)+'/skill',{name:name.value.trim()});await refresh();});
   const forget=document.createElement('button');forget.type='button';forget.textContent='Forget procedure';forget.className='reject';forget.onclick=()=>perform(async()=>{await api('memory/'+encodeURIComponent(entry.id),undefined,'DELETE');await refresh();});row.append(save,forget);item.append(name,row);box.append(item);
  }
 }};
};
