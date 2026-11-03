/* An authenticated view of the existing isolated Agent browser. */
window.installAgentBrowserPanel=({api,perform,selectedRun,refresh,token})=>{
 const panel=document.createElement('section');panel.id='agent-browser';panel.className='card';
 panel.innerHTML='<h2>Browser</h2><p>Browse public websites in an isolated session for the selected task. Navigation and interactions follow your action approvals. Your personal browser accounts are not shared.</p><label>Website address<input type="url" id="agent-browser-url" placeholder="https://example.com" autocomplete="off"></label><div class="row"><button id="agent-browser-open">Open page</button><button id="agent-browser-read">Read page</button><button id="agent-browser-refresh">Refresh preview</button><button id="agent-browser-close">Close page</button></div><p id="agent-browser-status" role="status">Select a task to browse with Sakura.</p><img id="agent-browser-image" alt="Current isolated browser viewport" hidden style="display:block;max-width:100%;border:1px solid var(--ag-line,#536372);border-radius:10px"><div id="agent-browser-elements"></div><details><summary>Page text</summary><pre id="agent-browser-text" style="white-space:pre-wrap;overflow-wrap:anywhere;max-height:320px;overflow:auto"></pre></details>';
 document.querySelector('main').append(panel);
 const style=document.createElement('style');style.textContent='#agent-browser[hidden],#agent-browser-image[hidden]{display:none!important}#agent-browser-elements{max-height:360px;overflow:auto;margin-top:12px}#agent-browser-elements .row{padding:6px 0}#agent-browser-elements button{overflow-wrap:anywhere;white-space:normal}';panel.prepend(style);
 const $=id=>panel.querySelector('#agent-browser-'+id);
 const localFrame=document.createElement('iframe');localFrame.id='agent-local-app';localFrame.title='Local app inside Sakura';localFrame.hidden=true;
 localFrame.setAttribute('sandbox','allow-scripts allow-forms allow-same-origin allow-downloads');
 localFrame.setAttribute('referrerpolicy','no-referrer');localFrame.style.cssText='width:100%;height:70vh;min-height:360px;border:1px solid var(--ag-line,#536372);border-radius:10px;background:white';
 $('status').after(localFrame);
 function openLocal(address){
  const url=new URL(address);if(!['http:','https:'].includes(url.protocol)||!['localhost','127.0.0.1','[::1]'].includes(url.hostname)||url.username||url.password)throw Error('Use a loopback app address without credentials.');
  localFrame.src=url.href;localFrame.hidden=false;$('url').value=url.href;
  $('status').textContent='Local app opened inside Sakura. If it refuses embedding, change that app’s frame policy; Sakura will not launch Chrome.';
  window.dispatchEvent(new Event('sakura-agent-browser-view'));
 }
 let signature='',objectURL='',ticket=0,currentID='';
 const clip=document.createElement('button');clip.type='button';clip.textContent='Save page reference with context';clip.onclick=()=>{window.dispatchEvent(new CustomEvent('sakura-save-context',{detail:{id:'',type:'link',url_or_path:$('url').value,topic:'',goal:'',emotion:'',tag_origin:'pending'}}));};$('open').after(clip);
 const clear=()=>{ticket++;signature='';currentID='';localFrame.hidden=true;localFrame.removeAttribute('src');delete localFrame.dataset.step;if(objectURL)URL.revokeObjectURL(objectURL);objectURL='';$('image').hidden=true;$('image').removeAttribute('src');$('elements').replaceChildren();$('text').textContent='';};
 async function propose(tool,args){
  const run=selectedRun();if(!run?.id)throw Error('Create or select a task first. Browser actions belong to that task.');
  await api('tasks/'+encodeURIComponent(run.id)+'/propose',{tool,arguments:args,reason:'Requested in the Sakura browser panel.'});
  await refresh();window.dispatchEvent(new Event('sakura-agent-task-view'));
 }
 async function preview(){
  const id=selectedRun()?.id;if(!id)return;
  const turn=++ticket;
  try{
   const response=await fetch('/api/agent/browser/'+encodeURIComponent(id)+'/preview',{headers:{'X-Sakura-Agent':token},cache:'no-store'});
   if(!response.ok)throw Error('No active browser page. Open a website and approve the action first.');
   const blob=await response.blob();if(turn!==ticket||id!==selectedRun()?.id)return;
   if(objectURL)URL.revokeObjectURL(objectURL);objectURL=URL.createObjectURL(blob);$('image').src=objectURL;$('image').hidden=false;
   $('status').textContent='Preview captured. Page interactions use the numbered controls below.';
  }catch(error){if(turn===ticket){$('image').hidden=true;$('status').textContent=error.message;}}
 }
 $('open').onclick=()=>perform(async()=>{const url=new URL($('url').value);if(!['http:','https:'].includes(url.protocol)||url.username||url.password)throw Error('Use an HTTP(S) website address without credentials.');await propose(['localhost','127.0.0.1','[::1]'].includes(url.hostname)?'local_app.open':'browser.open',{url:url.href});});
 $('read').onclick=()=>localFrame.hidden?perform(()=>propose('browser.read',{})):$('status').textContent='Interact with the local app directly below. Read page applies to isolated public websites.';
 $('close').onclick=()=>localFrame.hidden?perform(()=>propose('browser.close',{})):(localFrame.hidden=true,localFrame.removeAttribute('src'),$('status').textContent='Local app view closed. Its server continues running.');$('refresh').onclick=()=>localFrame.hidden?preview():localFrame.src=localFrame.src;
 function render(run){
  if(currentID!==run?.id){clear();currentID=run?.id||'';}
  const local=(run?.steps||[]).findLast(s=>s.tool==='local_app.open'&&s.status==='completed'&&s.result?.ok&&s.result?.presentation==='sakura-browser');
  if(local&&localFrame.dataset.step!==local.id){localFrame.dataset.step=local.id;openLocal(local.result.url);}
  const step=(run?.steps||[]).findLast(s=>s.status==='completed'&&s.tool?.startsWith('browser.'));
  if(local&&!localFrame.hidden&&(!step||run.steps.indexOf(local)>run.steps.indexOf(step)))return;
  if(!step){$('status').textContent='Select a task, enter a website and approve Open page.';return;}
  if(signature===step.id)return;signature=step.id;
  if(step.result?.url)fetch('/api/features/revisit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:step.result.url})}).then(r=>r.ok?r.json():{}).then(value=>{if(value.match)$('status').textContent=value.match.message;}).catch(()=>{});
  if(step.tool==='browser.close'){clear();$('status').textContent='Browser closed; its session cookies were discarded.';return;}
  const result=step.result;if(!result?.snapshot)return;
  localFrame.hidden=true;localFrame.removeAttribute('src');
  $('url').value=result.url||'';$('text').textContent=result.text||'';$('elements').replaceChildren();
  for(const item of result.elements||[]){
   const row=document.createElement('div');row.className='row';const b=document.createElement('button');b.type='button';
   b.textContent=item.element+' · '+String(item.label||item.text||item.name||item.tag).slice(0,110);
   const secret=['password','file','hidden'].includes(String(item.type).toLowerCase());b.disabled=secret;
   b.onclick=()=>perform(()=>propose('browser.click',{snapshot:result.snapshot,element:item.element}));row.append(b);
   if(['INPUT','TEXTAREA'].includes(item.tag)&&!secret){const input=document.createElement('input');input.maxLength=4000;input.autocomplete='off';input.setAttribute('aria-label','Text for element '+item.element);const fill=document.createElement('button');fill.type='button';fill.textContent='Fill';fill.onclick=()=>perform(()=>propose('browser.fill',{snapshot:result.snapshot,element:item.element,text:input.value}));row.append(input,fill);}
   $('elements').append(row);
  }
  void preview();
 }
 const routeLink=event=>{const anchor=event.target.closest?.('a[href]');if(!anchor||anchor.hasAttribute('download')||event.defaultPrevented||event.button!==0)return;let url;try{url=new URL(anchor.href);}catch{return;}if(!['http:','https:'].includes(url.protocol)||url.origin===location.origin)return;event.preventDefault();$('url').value=url.href;window.dispatchEvent(new Event('sakura-agent-browser-view'));void $('open').onclick();};
 document.addEventListener('click',routeLink);
 window.addEventListener('pagehide',()=>{clear();document.removeEventListener('click',routeLink);},{once:true});return {render,openLocal};
};
