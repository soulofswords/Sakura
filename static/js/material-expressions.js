import {tintEdit,opacityEdit} from './part-appearance.js?v=1';

// One active preset per material/channel; tint and opacity remain independent.
export function applyMaterialPreset(current,preset,enabled){
 const value=enabled?preset.value:preset.before;
 return preset.channel==='opacity'?opacityEdit(current,value):tintEdit(current,value.color,value.strength);
}
export function installMaterialExpressions(api){
 const host=document.querySelector('[data-model-panel="expression"]');
 const card=document.createElement('section');card.className='setting-group';card.id='material-expressions';
 const heading=document.createElement('h3');heading.textContent='Part color & transparency expressions';
 const note=document.createElement('p');note.className='modal-hint';note.textContent='Pick a part in Texture coloring, choose color or transparency and set its values. Name the preset and save it. Toggle it here whenever you need it; the other material channel stays unchanged.';
 const list=document.createElement('div');list.id='material-expression-list';
 card.append(heading,note,list);host.append(card);
 const saveBox=document.createElement('div');saveBox.className='setting-group';
 const name=document.createElement('input');name.id='material-expression-name';name.placeholder='Preset name (e.g. Hide jacket)';name.maxLength=80;name.setAttribute('aria-label','Part expression name');
 const save=document.createElement('button');save.type='button';save.id='save-material-expression';save.textContent='Save selected part as expression';
 const status=document.createElement('p');status.className='modal-hint';status.id='material-expression-status';status.setAttribute('role','status');
 saveBox.append(name,save,status);document.getElementById('model-color-reset').after(saveBox);
 let key='',items=[];
 const persist=()=>localStorage.setItem('sakura_material_expressions:'+key,JSON.stringify(items));
 function refresh(){const next=api.key();if(next!==key){key=next;try{items=JSON.parse(localStorage.getItem('sakura_material_expressions:'+key)||'[]');if(!Array.isArray(items))items=[];}catch{items=[];}}render();}
 function channelValue(current,channel){return channel==='opacity'?(current?.opacity??1):{color:current?.color||'#ffffff',strength:current?.strength??0};}
 function set(preset,on){const c=api.controller();if(!c?.entry(preset.part))throw Error('That model part is unavailable. Load the matching model.');
  if(on){for(const other of items)if(other!==preset&&other.active&&other.part===preset.part&&other.channel===preset.channel)set(other,false);preset.before=channelValue(c.colors[preset.part],preset.channel);}
  c.setColor(preset.part,applyMaterialPreset(c.colors[preset.part],preset,on));preset.active=on;api.save();persist();api.changed();
 }
 function render(){list.replaceChildren();const c=api.controller();for(const p of items){const row=document.createElement('div');row.className='setting-group';const label=document.createElement('p');label.textContent=p.name+' · '+(c?.entry(p.part)?.name||p.part)+' · '+p.channel;
   const toggle=document.createElement('button');toggle.type='button';toggle.setAttribute('role','switch');toggle.setAttribute('aria-checked',String(!!p.active));toggle.textContent=p.active?'On · turn off':'Off · turn on';toggle.onclick=()=>{try{set(p,!p.active);render();}catch(e){status.textContent=e.message;}};
   const remove=document.createElement('button');remove.type='button';remove.textContent='Delete preset';remove.onclick=()=>{try{if(p.active)set(p,false);items=items.filter(x=>x!==p);persist();render();}catch(e){status.textContent=e.message;}};row.append(label,toggle,remove);list.append(row);
  }if(!items.length){const empty=document.createElement('p');empty.textContent='No part expressions saved for this model.';list.append(empty);}}
 save.onclick=()=>{try{const c=api.controller(),part=api.part(),edit=api.edit();if(!c?.entry(part)||!key)throw Error('Load a model and select a part first.');if(!name.value.trim())throw Error('Enter a preset name.');if(items.length>=40)throw Error('Delete an old preset first (limit 40).');
   const p={id:crypto.randomUUID(),name:name.value.trim(),part,channel:edit.channel,value:edit.value,active:false};items.push(p);set(p,true);name.value='';persist();render();status.textContent='Saved and enabled. Open Expressions to switch this part effect on or off.';
  }catch(e){status.textContent=e.message;}};
 return {refresh};
}
