export function installHotkeyDeckControls(){
 const host=document.getElementById('tab-general');if(!host)return;
 const panel=document.createElement('fieldset');panel.className='setting-group';panel.innerHTML='<legend>Sakura Mobile hotkey deck</legend><p>Bind phone buttons here to an OBS scene or avatar pose. Only these saved bindings can run from a paired phone. OBS WebSocket must be enabled on this PC.</p><label>OBS WebSocket port<input id="deck-port" type="number" min="1024" max="65535" value="4455"></label><label>OBS password<input id="deck-password" type="password" autocomplete="new-password" placeholder="Leave blank to keep saved password"></label><button type="button" id="deck-scenes">List OBS scenes</button><div id="deck-rows"></div><button type="button" id="deck-add">Add phone button</button><button type="button" id="deck-save">Save deck</button><p id="deck-status" role="status"></p>';host.append(panel);
 const $=id=>panel.querySelector('#deck-'+id),poses=['greeting_wave','hands_both','hand_left','hand_right','groove','step','wave','twist','disco','march','stop'];
 async function api(path,body){const res=await fetch('/api/hotkey-deck'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const data=await res.json();if(!res.ok)throw Error(data.error||'Deck setup failed.');return data;}
 function row(slot={id:crypto.randomUUID().replaceAll('-',''),label:'New button',kind:'pose',target:'greeting_wave'}){
  if($('rows').children.length>=24)return;const box=document.createElement('div');box.dataset.slot=slot.id;box.style.margin='12px 0';
  const label=document.createElement('input');label.value=slot.label;label.maxLength=60;label.setAttribute('aria-label','Phone button label');
  const kind=document.createElement('select');kind.append(new Option('Avatar pose','pose'),new Option('OBS scene','scene'));kind.value=slot.kind;
  const target=document.createElement('input');target.value=slot.target;target.maxLength=200;target.setAttribute('aria-label','Exact scene name or pose');target.placeholder=poses.join(', ');
  const remove=document.createElement('button');remove.type='button';remove.textContent='Remove button';remove.onclick=()=>box.remove();box.append(label,kind,target,remove);$('rows').append(box);
 }
 $('add').onclick=()=>row();$('save').onclick=async()=>{try{const slots=[...$('rows').children].map(box=>{const [label,kind,target]=box.querySelectorAll('input,select');return{id:box.dataset.slot,label:label.value,kind:kind.value,target:target.value};});await api('',{port:Number($('port').value),password:$('password').value,slots});$('password').value='';$('status').textContent='Saved. The deck appears in Sakura Mobile when this PC is connected.';}catch(e){$('password').value='';$('status').textContent=e.message;}};
 $('scenes').onclick=async()=>{try{$('status').textContent=(await api('/scenes')).scenes.map(s=>s.sceneName).join(' · ')||'OBS has no scenes.';}catch(e){$('status').textContent=e.message;}};
 void api('').then(data=>{$('port').value=data.port;data.slots.forEach(row);}).catch(e=>{$('status').textContent=e.message;});
}
