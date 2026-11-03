/* Companion-mode presentation layer. Existing controls retain IDs, handlers and APIs. */
import {installSpeakerEnrolment} from './speaker-enrolment.js?v=1';
const ICONS={
 character:'<circle cx="12" cy="8" r="4"/><path d="M4 22v-3a8 8 0 0 1 16 0v3"/>',
 camera:'<rect x="3" y="6" width="18" height="15" rx="3"/><path d="m8 6 2-3h4l2 3"/><circle cx="12" cy="13" r="4"/>',
 voice:'<path d="M11 5 6 9H3v6h3l5 4V5Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>',
 tools:'<path d="m14 7 3 3-9 9-3-3 9-9Z"/><path d="m17 4 3 3-2 2-3-3 2-2Z"/><path d="M5 19H4v-1"/>',
 background:'<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="2"/><path d="m3 17 6-6 4 4 3-3 5 5"/>',
 output:'<rect x="2" y="5" width="14" height="14" rx="3"/><path d="m16 10 6-4v12l-6-4"/>',
 phone:'<rect x="6" y="2" width="12" height="20" rx="3"/><path d="M10 18h4"/>',
 memory:'<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3Z"/><path d="m9 12 2 2 4-4"/>',
 settings:'<path d="m10 2-1 3-3 1-3-1-2 4 2 2v3l-2 2 2 4 3-1 3 1 1 3h4l1-3 3-1 3 1 2-4-2-2v-3l2-2-2-4-3 1-3-1-1-3Z"/><circle cx="12" cy="12" r="3"/>',
 theme:'<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 0 0 18c1.5 0 2-1 2-2s-.5-2 1-2h2a4 4 0 0 0 4-4 9 9 0 0 0-9-10Z"/>'
};
const svg=name=>`<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[name]||ICONS.settings}</svg>`;
export function installCompanionStudio(){
 if(document.getElementById('companion-studio'))return;
 const byId=id=>document.getElementById(id);
 const root=document.createElement('section');root.id='companion-studio';root.hidden=true;root.setAttribute('aria-label','Sakura Companion studio');
 const entries=[['character','Models','#f7dce8','#b7688d'],['camera','Camera & tracking','#d9effb','#3888b3'],['voice','Voice & speech','#d9effb','#3888b3'],['tools','Model Settings','#e3f3da','#76a85c'],['background','Background & stage items','#e3f3da','#76a85c'],['output','Streaming & output','#dce7fa','#6480b5'],['phone','Sakura Mobile','#fae8d1','#b9894a'],['memory','Memory & privacy','#e9e2fa','#8d6abb'],['settings','Settings','#f7dce8','#b7688d']];
 const dockButton=([key,label,tint,ink])=>`<button type="button" class="studio-dock-button" data-companion-pane="${key}" data-label="${label}" title="${label}" aria-label="${label}" aria-pressed="false" aria-controls="companion-panel" style="--dock-tint:${tint};--dock-ink:${ink}">${svg(key)}</button>`;
 root.innerHTML=`<nav id="companion-dock" aria-label="Companion tools">${entries.map(dockButton).join('')}</nav>
 <aside id="companion-panel" hidden aria-labelledby="companion-panel-title"><header class="studio-panel-header"><div><small>SAKURA COMPANION</small><h2 id="companion-panel-title">Character</h2></div><button id="companion-panel-close" type="button" aria-label="Close panel">×</button></header><div class="studio-panel-body">
 <div data-companion-content="character" hidden><section class="studio-card"><h3>Your character library</h3><input id="companion-model-search" type="search" aria-label="Search imported characters" placeholder="Search your characters…"><div id="companion-model-results" hidden></div><div data-companion-port="model-dropdown"></div><div data-companion-port="vrm-dropdown"></div><div data-companion-port="live2d-dropdown"></div><p>Select a character above, or import a complete model package below.</p></section><section class="studio-card"><h3>Import a character</h3><div class="studio-actions" data-companion-port="imports"></div><p>PMX and Live2D need their texture folders. VRM uses a single .vrm file.</p></section><section class="studio-card"><h3>Framing & customization</h3><div data-companion-port="size"></div><div class="studio-actions" data-companion-port="framing"></div></section></div>
 <div data-companion-content="camera" hidden><section class="studio-card"><h3>Give Sakura the camera</h3><div class="studio-camera-choices"><button type="button" data-companion-camera="objects" aria-pressed="false"><strong>See objects</strong><span>Lens-style: show her something and she describes it</span></button><button type="button" data-companion-camera="tracking" aria-pressed="false"><strong>Track my face &amp; hands</strong><span>Add-on: your movement drives the avatar while chat stays on</span></button></div><div data-companion-port="camera-device"></div><div data-companion-port="camera"></div><h4>AI VTuber cohost</h4><div class="studio-actions" data-companion-port="cohost"></div><p>Companion-only: respond to livestream chat and screen events. This is separate from camera tracking and the standalone VTuber app.</p><p>Only one camera task runs at a time. Object frames go to your AI provider; face and hand tracking stay on this PC.</p></section></div>
 <div data-companion-content="voice" hidden><section class="studio-card"><h3>Voice & speech</h3><h4>Conversation mode</h4><div class="studio-actions" role="group" aria-label="Conversation mode"><button type="button" data-companion-style="friend" role="switch" aria-label="Friend" aria-checked="true"><span>Friend</span><span class="conversation-switch-track" aria-hidden="true"></span><span data-style-state aria-hidden="true">On</span></button><button type="button" data-companion-style="teacher" role="switch" aria-label="Teacher" aria-checked="false"><span>Teacher</span><span class="conversation-switch-track" aria-hidden="true"></span><span data-style-state aria-hidden="true">Off</span></button></div><p id="companion-style-status" role="status">Friend: warm, casual conversation.</p><h4 style="margin-top:14px">Conversation tone (wording)</h4><p>Mild is calm, Flirty adds playful affection, and Bold adds stronger teasing. This changes reply wording, not the TTS voice or room movement.</p><div class="studio-actions" role="group" aria-label="Delivery intensity"><button type="button" data-companion-spice="mild" aria-pressed="true">Mild</button><button type="button" data-companion-spice="flirty" aria-pressed="false">Flirty</button><button type="button" data-companion-spice="bold" aria-pressed="false">Bold</button></div><p id="companion-spice-status" role="status">Mild: warm and understated. This changes only how replies are worded, never what she claims.</p><label>Reply emotions<select id="companion-emotion"><option value="auto">Automatic · match the reply</option><option value="off">Off · neutral</option><option value="happy">Happy</option><option value="concerned">Concerned</option><option value="amused">Amused</option><option value="surprised">Surprised</option><option value="focused">Focused</option></select></label><p id="companion-emotion-status" role="status">Facial reactions use expressions supported by the current model. Independent of screen viewing. Manual expressions and tracking take priority.</p><div data-companion-port="voice"></div><div class="studio-actions" data-companion-port="speech"></div><div class="studio-actions" style="margin-top:10px"><button type="button" data-companion-action="voice-library">Voice library</button><button type="button" data-companion-action="mouth">Mouth & lip sync</button></div></section></div>
 <div data-companion-content="tools" hidden><section class="studio-card"><h3>Movement & dance</h3><div data-companion-port="dance"></div><div class="studio-actions" data-companion-port="dance-buttons"></div></section><section class="studio-card"><h3>Screen & games</h3><div class="studio-actions" data-companion-port="screen"></div><p>Screen viewing, reactions and game detection run locally and only while enabled.</p></section><section class="studio-card"><h3>Stage & extras</h3><div class="studio-actions"><button type="button" data-companion-action="stage-library">3D stages</button><button type="button" data-companion-action="prop-library">Tools &amp; Props</button><button type="button" data-companion-action="stage-items">Image &amp; Live2D items</button></div><p>Open the background panel to add scenery and items alongside your character.</p></section></div>
 <div data-companion-content="output" hidden><section class="studio-card"><h3>Virtual camera</h3><div class="studio-actions" data-companion-port="virtual-camera"></div><p>Install the Sakura camera driver here, then pick Sakura Virtual Camera in Discord, Zoom or OBS.</p></section><div data-companion-port="spout"></div></div>
 <div data-companion-content="phone" hidden><div data-companion-port="phone"></div><section class="studio-card"><h3>Use your phone camera</h3><div class="studio-actions" data-companion-port="phone-buttons"></div><p>Open Sakura Mobile, choose this PC from the list and enter its 6-digit pairing code. Keep Sakura Mobile open.</p></section></div>
 <div data-companion-content="memory" hidden><section class="studio-card"><h3>Memory & privacy</h3><div class="studio-actions" data-companion-port="memory"></div><p>Clearing memory forgets saved conversations on this computer. Imported models, voices and artwork are kept.</p></section></div>
 </div></aside>
 <div id="companion-statusbar"><span class="studio-status-text" id="companion-status-text" role="status">Talk to Sakura…</span><button id="companion-vtuber-switch" type="button">VTuber mode</button><button id="companion-agent-switch" type="button">Agent mode</button></div>`;
 document.body.append(root);
 installSpeakerEnrolment(root.querySelector('[data-companion-content="voice"]'));
 const toolsContent=root.querySelector('[data-companion-content="tools"]');
 const memoryContent=root.querySelector('[data-companion-content="memory"]');
 memoryContent.append(...toolsContent.children);toolsContent.remove();
 const backgroundContent=document.createElement('div');backgroundContent.dataset.companionContent='background';backgroundContent.hidden=true;
 backgroundContent.innerHTML='<section class="studio-card"><h3>Stage background</h3><div data-companion-port="background"></div><div class="studio-actions" data-companion-port="transparency"></div></section>';
 panelRoot(root).append(backgroundContent);
 const panel=byId('companion-panel'),portals=[];let active=false,currentPane='';
 const nativeModals=['settings-modal','expression-modal','tracking-modal'];
 // Resize the model editor independently of the app window and chat panel.
 for(const editorId of ['expression-modal','settings-modal']){
 const editor=byId(editorId),editorCard=editor?.querySelector('.modal-card');
 if(editorCard){
  const handle=document.createElement('button');handle.type='button';handle.className='companion-editor-resize';
  const title=editorId==='settings-modal'?'Settings':'Model Settings';
  handle.setAttribute('aria-label','Resize '+title);handle.title='Drag to resize '+title;handle.textContent='↔';editorCard.append(handle);
  let drag=null;
  const resize=(width,height)=>{
   const rect=editor.getBoundingClientRect();
   const left=document.body.classList.contains('companion-panel-left');
   const available=left?innerWidth-rect.left-12:rect.right-12;
   editor.style.setProperty('width',Math.min(Math.max(260,width),available)+'px','important');
   editor.style.setProperty('height',Math.min(Math.max(300,height),innerHeight-rect.top-16)+'px','important');
   editor.style.setProperty('bottom','auto','important');
  };
  handle.addEventListener('pointerdown',event=>{
   if(!active)return;const rect=editor.getBoundingClientRect();drag={x:event.clientX,y:event.clientY,width:rect.width,height:rect.height,left:document.body.classList.contains('companion-panel-left')};
   handle.setPointerCapture(event.pointerId);event.preventDefault();
  });
  handle.addEventListener('pointermove',event=>{if(drag)resize(drag.width+(event.clientX-drag.x)*(drag.left?1:-1),drag.height+event.clientY-drag.y);});
  const finish=()=>{drag=null;};handle.addEventListener('pointerup',finish);handle.addEventListener('pointercancel',finish);
  handle.addEventListener('keydown',event=>{
   if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;
   const rect=editor.getBoundingClientRect();resize(rect.width+(event.key==='ArrowRight'?24:event.key==='ArrowLeft'?-24:0),rect.height+(event.key==='ArrowDown'?24:event.key==='ArrowUp'?-24:0));event.preventDefault();
  });
  window.addEventListener('resize',()=>{if(active&&editor.style.height){const rect=editor.getBoundingClientRect();resize(rect.width,rect.height);}});
 }
 }
 let styleRevision=0;
 const styleButtons=[...root.querySelectorAll('[data-companion-style]')];
 function showConversationStyle(mode){for(const button of styleButtons){const on=button.dataset.companionStyle===mode;button.setAttribute('aria-checked',String(on));button.querySelector('[data-style-state]').textContent=on?'On':'Off';}byId('companion-style-status').textContent=mode==='teacher'?'Teacher: patient explanations, useful examples and step-by-step guidance.':'Friend: warm, casual conversation.';}
 async function readConversationStyle(){const revision=styleRevision;try{const response=await fetch('/api/settings');if(!response.ok)throw Error('Could not read conversation mode.');const data=await response.json();if(revision===styleRevision)showConversationStyle(data.conversation_mode||'friend');}catch(error){if(revision===styleRevision)byId('companion-style-status').textContent=error.message;}}
 async function setConversationStyle(mode){++styleRevision;for(const button of styleButtons)button.disabled=true;try{const response=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({conversation_mode:mode})});const data=await response.json();if(!response.ok)throw Error(data.error||'Could not save conversation mode.');showConversationStyle(mode);}catch(error){byId('companion-style-status').textContent=error.message;}finally{for(const button of styleButtons)button.disabled=false;}}
 for(const button of styleButtons)button.onclick=()=>void setConversationStyle(button.getAttribute('aria-checked')==='true'?(button.dataset.companionStyle==='friend'?'teacher':'friend'):button.dataset.companionStyle);
 const SPICE_COPY={mild:'Mild: warm and understated.',flirty:'Flirty: playful and affectionate in casual chat; factual and task answers stay plain.',bold:'Bold: confident, teasing and openly flirtatious in casual chat; serious questions and stated boundaries end it.'};
 let spiceRevision=0,emotionRevision=0;
 const spiceButtons=[...root.querySelectorAll('[data-companion-spice]')];
 function showDeliverySpice(level){for(const button of spiceButtons)button.setAttribute('aria-pressed',String(button.dataset.companionSpice===level));byId('companion-spice-status').textContent=(SPICE_COPY[level]||SPICE_COPY.mild)+' This changes only how replies are worded, never what she claims.';}
 async function readDeliverySpice(){const revision=spiceRevision,emotionRead=emotionRevision;try{const response=await fetch('/api/settings');if(!response.ok)throw Error('Could not read delivery intensity.');const data=await response.json();if(revision===spiceRevision){showDeliverySpice(data.delivery_spice||'mild');if(emotionRead===emotionRevision)byId('companion-emotion').value=data.avatar_emotion||'auto';}}catch(error){if(revision===spiceRevision)byId('companion-spice-status').textContent=error.message;}}
 async function setDeliverySpice(level){++spiceRevision;for(const button of spiceButtons)button.disabled=true;try{const response=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({delivery_spice:level})});const data=await response.json();if(!response.ok)throw Error(data.error||'Could not save delivery intensity.');showDeliverySpice(level);}catch(error){byId('companion-spice-status').textContent=error.message;}finally{for(const button of spiceButtons)button.disabled=false;}}
 for(const button of spiceButtons)button.onclick=()=>void setDeliverySpice(button.dataset.companionSpice);
 byId('companion-emotion').onchange=async event=>{const select=event.target,value=select.value;++emotionRevision;select.disabled=true;try{const response=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({avatar_emotion:value})});const data=await response.json();if(!response.ok)throw Error(data.error||'Could not save reply emotion.');window.dispatchEvent(new CustomEvent('sakura-reply-emotion',{detail:{value}}));byId('companion-emotion-status').textContent=select.value==='off'?'Reply emotions off. Lip sync and manual expressions still work.':'Reply emotion: '+select.options[select.selectedIndex].text+'. Requires a matching expression in the model.';}catch(error){byId('companion-emotion-status').textContent=error.message;}finally{select.disabled=false;}};
 const click=id=>byId(id)?.click();
 const setHidden=(el,hidden)=>{if(el&&el.hidden!==hidden)el.hidden=hidden;};
 function markPane(key){
  currentPane=key;
  document.body.classList.remove('companion-panel-left');
  for(const b of root.querySelectorAll('[data-companion-pane]'))b.setAttribute('aria-pressed',String(b.dataset.companionPane===key));
 }
 function showPane(key){
  hideNative();
  setHidden(panel,false);
  for(const el of root.querySelectorAll('[data-companion-content]'))setHidden(el,el.dataset.companionContent!==key);
  byId('companion-panel-title').textContent=entries.find(e=>e[0]===key)?.[1]||key;markPane(key);
  if(key==='camera'){syncCameraButtons();window.dispatchEvent(new Event('sakura-camera-style-refresh'));}
  if(key==='voice'){void readConversationStyle();void readDeliverySpice();}
 }
 function hideNative(except=''){
  for(const [id,close] of [['settings-modal','close-settings-btn'],['expression-modal','close-expression-modal'],['tracking-modal','close-tracking-modal']]){
   if(id!==except&&!byId(id)?.classList.contains('hidden'))click(close);
  }
 }
 function closePanel(){setHidden(panel,true);hideNative();markPane('');}
 function nativeSettings(tab,key='settings'){closePanel();click('settings-btn');document.querySelector(`#settings-modal .tab-btn[data-tab="${tab}"]`)?.click();markPane(key);}
 function openPane(key){
  if(!active)return;
  if(key==='settings'){nativeSettings('general');markPane(key);return;}
  if(key==='tools'){closePanel();click('expression-editor-btn');document.querySelector('[data-model-tab="coloring"]')?.click();markPane(key);return;}
  showPane(key);
 }
 // Both studio shells port the same toolbar controls, so a node can leave with
 // the other one while our anchor stays put. Re-append it instead of trusting
 // the bookkeeping, and never restore a node the other shell is displaying.
 function move(node,slot){
  if(!node||!slot)return;
  const port=root.querySelector(`[data-companion-port="${slot}"]`);
  if(!port||port.contains(node)||node.closest('#vtuber-studio'))return;
  if(!portals.some(p=>p.node===node)){
   const anchor=document.createComment('Sakura companion: restore '+(node.id||slot));node.before(anchor);portals.push({node,anchor});
  }
  port.append(node);
 }
 const search=byId('companion-model-search'),results=byId('companion-model-results');
 function searchModels(){
  const q=search.value.trim().toLocaleLowerCase();results.replaceChildren();results.hidden=!q;if(!q)return;
  let count=0;
  for(const id of ['model-select','vrm-select','live2d-select']){
   const select=byId(id);if(!select)continue;
   for(const option of select.options){
    if(!option.value||option.disabled||!option.textContent.toLocaleLowerCase().includes(q))continue;
    if(count++>=30)continue;
    const button=document.createElement('button');button.type='button';button.textContent=({"model-select":"PMX","vrm-select":"VRM","live2d-select":"Live2D"}[id]+' · '+option.textContent);button.style.cssText='display:block;width:100%;text-align:left;margin-bottom:6px';
    button.onclick=()=>{select.value=option.value;select.dispatchEvent(new Event('change',{bubbles:true}));search.value='';results.hidden=true;};results.append(button);
   }
  }
  if(!count){const hint=document.createElement('p');hint.textContent='No imported character matches. Import a model below.';results.append(hint);}
 }
 search.addEventListener('input',searchModels);
 function portControls(){
  for(const id of ['model-dropdown','vrm-dropdown','live2d-dropdown'])move(byId(id),id);
  move(byId('settings-tracking-camera')?.closest('.camera-phone-row'),'camera-device');
  move(byId('companion-camera-group'),'camera');
  for(const id of ['upload-pmx-toolbar','upload-vrm-toolbar','upload-live2d-toolbar','refresh-models'])move(byId(id),'imports');
  move(byId('model-size')?.closest('label'),'size');
  for(const id of ['full-model-btn','quality-btn','eye-tracking-btn','pmx-editor-btn','mmd-btn'])move(byId(id),'framing');
  move(byId('voice-dropdown'),'voice');
  for(const id of ['interrupt-btn'])move(byId(id),'speech');
  move(byId('dance-style')?.closest('label'),'dance');
  for(const id of ['dance-btn','dance-stop-btn'])move(byId(id),'dance-buttons');
  for(const id of ['screen-view-btn','screen-react-btn','auto-game-btn','game-play-mode-control'])move(byId(id),'screen');
  move(byId('vtuber-mode-btn'),'cohost');
  move(byId('send-model-mobile'),'phone-buttons');
  move(byId('obs-background-enabled')?.closest('.setting-group'),'background');
  move(byId('bg-toggle-btn'),'transparency');
  move(byId('virtual-camera-toggle'),'virtual-camera');
  move(byId('spout-enabled')?.closest('fieldset'),'spout');
  move(byId('phone-link-enabled')?.closest('fieldset'),'phone');
  for(const id of ['connect-phone-btn'])move(byId(id),'phone-buttons');
  for(const id of ['clear-memory-desktop'])move(byId(id),'memory');
 }
 function syncCameraButtons(){
  const select=byId('companion-camera-mode'),toggle=byId('companion-camera-enabled');
  for(const button of root.querySelectorAll('[data-companion-camera]'))button.setAttribute('aria-pressed',String(!!toggle?.checked&&select?.value===button.dataset.companionCamera));
 }
 // The camera is one task at a time: picking a choice turns the other one off,
 // and clicking the running choice switches the camera back off.
 function setCameraChoice(mode){
  const select=byId('companion-camera-mode'),toggle=byId('companion-camera-enabled');
  if(!select||!toggle)return;
  if(select.value===mode&&toggle.checked){
   toggle.checked=false;toggle.dispatchEvent(new Event('change',{bubbles:true}));
  }else{
   const changed=select.value!==mode;
   if(changed)select.value=mode;
   // A running camera restarts through the mode select; a stopped one only
   // needs the toggle, so it must not start twice from two change events.
   if(!toggle.checked){toggle.checked=true;toggle.dispatchEvent(new Event('change',{bubbles:true}));}
   else if(changed)select.dispatchEvent(new Event('change',{bubbles:true}));
  }
  syncCameraButtons();
 }
 for(const id of ['companion-camera-mode','companion-camera-enabled'])byId(id)?.addEventListener('change',syncCameraButtons);
 function restoreControls(){
  for(let i=portals.length-1;i>=0;i--){
   const {node,anchor}=portals[i];
   // The VTuber shell may be displaying this control right now; taking it back
   // would empty that panel, so leave it and keep the anchor for a later move.
   if(!root.contains(node))continue;
   if(anchor.parentNode)anchor.replaceWith(node);
   portals.splice(i,1);
  }
 }
 // VTuber mode owns .studio-docked while tracking-only, so never fight it there.
 function syncDocked(){
  if(document.body.classList.contains('tracking-only'))return;
  for(const id of nativeModals)byId(id)?.classList.toggle('studio-docked',active);
 }
 function syncMode(){
  const enabled=(window.SAKURA_EDITION||'companion')!=='vtuber'&&!document.body.classList.contains('tracking-only')&&!document.body.classList.contains('agent-mode');
  if(enabled===active)return;
  active=enabled;document.body.classList.toggle('companion-ui-active',active);setHidden(root,!active);
  if(active){portControls();byId('companion-status-text').textContent=window.sakuraLatestReply||'Talk to Sakura…';}
  else{closePanel();restoreControls();for(const id of ['settings-modal','expression-modal'])for(const property of ['width','height','bottom'])byId(id)?.style.removeProperty(property);}
  syncDocked();syncStudioSwitch();
 }
 // The VTuber studio keeps its own status bar; offer the way back from there.
 function syncStudioSwitch(){
  const bar=byId('studio-statusbar');if(!bar)return;
  let button=byId('studio-companion-switch');
  if(!button){
   button=document.createElement('button');button.id='studio-companion-switch';button.type='button';button.textContent='Companion mode';
   button.onclick=()=>click('tracking-restore-ai');
   bar.insertBefore(button,bar.querySelector('button'));
  }
  button.hidden=!(document.body.classList.contains('tracking-only')&&(window.SAKURA_EDITION||'companion')!=='vtuber');
 }
 root.addEventListener('click',event=>{
  if(event.target.closest('#vtuber-mode-btn')){nativeSettings('assistant','camera');return;}
  const cameraChoice=event.target.closest('[data-companion-camera]');
  if(cameraChoice){setCameraChoice(cameraChoice.dataset.companionCamera);return;}
  const nav=event.target.closest('[data-companion-pane]');if(nav){const key=nav.dataset.companionPane;
   const visible=key==='settings'?!byId('settings-modal')?.classList.contains('hidden'):key==='tools'?!byId('expression-modal')?.classList.contains('hidden'):!panel.hidden;
   if(currentPane===key&&visible)closePanel();else openPane(key);return;}
  const action=event.target.closest('[data-companion-action]')?.dataset.companionAction;
  if(action==='voice-library')nativeSettings('voice','voice');
  else if(['stage-library','prop-library','stage-items'].includes(action)){
   showPane('background');
   const item=action==='stage-items',target=byId(item?'stage-items-card':'pmx-stage-card');
   if(!item){
    const kind=byId('pmx-stage-kind'),value=action==='prop-library'?'prop':'stage';
    if(kind&&kind.value!==value){kind.value=value;kind.dispatchEvent(new Event('change',{bubbles:true}));}
   }
   if(target){target.scrollIntoView({block:'start',behavior:'smooth'});byId(item?'stage-add-item':'pmx-stage-enabled')?.focus({preventScroll:true});}
  }
  else if(action==='mouth'){closePanel();click('expression-editor-btn');document.querySelector('[data-model-tab="mouth"]')?.click();markPane('voice');}
 });
 byId('companion-panel-close').onclick=closePanel;
 window.addEventListener('sakura-companion-reply',event=>{const text=event.detail?.text;if(typeof text==='string'){byId('companion-status-text').textContent=text;byId('companion-status-text').title=text;}});
 window.addEventListener('sakura-open-phone-panel',event=>{if(active){event.preventDefault();openPane('phone');}});
 window.addEventListener('sakura-open-conversation-mode',event=>{
  if(!active)return;event.preventDefault();openPane('voice');
  const mode=event.detail?.mode==='friend'?'friend':'teacher';
  const target=root.querySelector('[data-companion-style="'+mode+'"]');
  target?.scrollIntoView({block:'nearest'});target?.focus();
 });
 window.addEventListener('sakura-open-avatar-picker',event=>{if(!active)return;openPane('character');const search=byId('companion-model-search');search.value=event.detail?.cloud?'':event.detail?.query||'';search.dispatchEvent(new Event('input'));search.focus();if(event.detail?.cloud)window.dispatchEvent(new CustomEvent('sakura-open-cloud-library',{detail:{query:event.detail?.query||''}}));});
 byId('companion-vtuber-switch').onclick=()=>click('tracking-mode-btn');
 byId('companion-agent-switch').onclick=()=>click('agent-mode-toggle');
 document.addEventListener('keydown',event=>{if(active&&event.key==='Escape')closePanel();});
 new MutationObserver(()=>{syncMode();}).observe(document.body,{attributes:true,attributeFilter:['class']});
 syncMode();
 return {openPane,closePanel,isActive:()=>active};
}
function panelRoot(root){return root.querySelector('.studio-panel-body');}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>installCompanionStudio(),{once:true});else installCompanionStudio();
