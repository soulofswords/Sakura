/* VTuber-only presentation layer. Existing controls retain IDs, handlers and APIs. */
const ICONS={
 models:'<circle cx="12" cy="8" r="4"/><path d="M4 22v-3a8 8 0 0 1 16 0v3"/>',
 tracking:'<rect x="3" y="6" width="18" height="15" rx="3"/><path d="m8 6 2-3h4l2 3"/><circle cx="12" cy="13" r="4"/>',
 expressions:'<circle cx="12" cy="12" r="9"/><path d="M8 15s1 3 4 3 4-3 4-3M8 9h.01M16 9h.01"/>',
 background:'<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 6-6 4 4 3-3 5 5"/>',
 output:'<rect x="2" y="5" width="14" height="14" rx="3"/><path d="m16 10 6-4v12l-6-4"/>',
 phone:'<rect x="6" y="2" width="12" height="20" rx="3"/><path d="M10 18h4"/>',
 settings:'<path d="m10 2-1 3-3 1-3-1-2 4 2 2v3l-2 2 2 4 3-1 3 1 1 3h4l1-3 3-1 3 1 2-4-2-2v-3l2-2-2-4-3 1-3-1-1-3Z"/><circle cx="12" cy="12" r="3"/>',
 collab:'<circle cx="9" cy="8" r="3"/><path d="M2 21v-3a7 7 0 0 1 14 0v3M17 5a3 3 0 0 1 0 6M18 14a6 6 0 0 1 4 6"/>',
 lock:'<rect x="5" y="10" width="14" height="12" rx="3"/><path d="M8 10V6a4 4 0 0 1 8 0v4M12 15v3"/>',
 hide:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>'
};
const svg=name=>`<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[name]||ICONS.settings}</svg>`;
export function installVtuberStudio(){
 if(document.getElementById('vtuber-studio'))return;
 const byId=id=>document.getElementById(id);
 const root=document.createElement('section');root.id='vtuber-studio';root.hidden=true;root.setAttribute('aria-label','Sakura VTuber studio');
 const entries=[['models','Models','#f7dce8','#b7688d'],['tracking','Camera & tracking','#d9effb','#3888b3'],['expressions','Expressions & hotkeys','#e9e2fa','#8d6abb'],['background','Background','#e3f3da','#76a85c'],['output','Streaming & voice','#dce7fa','#6480b5'],['phone','Sakura Mobile','#fae8d1','#b9894a'],['settings','Settings','#f7dce8','#b7688d'],['collab','Collab','#e2e4fa','#797cb0']];
 root.innerHTML=`<nav id="studio-dock" aria-label="VTuber tools">${entries.map(([key,label,tint,ink])=>`<button type="button" class="studio-dock-button" data-studio-pane="${key}" data-label="${label}" title="${label}" aria-label="${label}" aria-pressed="false" aria-controls="studio-panel" style="--dock-tint:${tint};--dock-ink:${ink}">${svg(key)}</button>`).join('')}<button id="studio-model-lock" type="button" class="studio-dock-button studio-lock" data-label="Lock model position" title="Lock model position" aria-label="Lock model position" aria-pressed="false">${svg('lock')}</button><button id="studio-hide-ui" type="button" class="studio-dock-button studio-hide" data-label="Hide controls" title="Hide controls (Ctrl+Shift+H)" aria-label="Hide controls">${svg('hide')}</button></nav>
 <aside id="studio-panel" hidden aria-labelledby="studio-panel-title"><header class="studio-panel-header"><div><small>SAKURA STUDIO</small><h2 id="studio-panel-title">Models</h2></div><button id="studio-panel-close" type="button" aria-label="Close panel">×</button></header><div class="studio-panel-body">
 <div data-studio-content="models" hidden><section class="studio-card"><h3>Your character library</h3><input id="studio-model-search" type="search" aria-label="Search imported characters" placeholder="Search your characters…"><div id="studio-model-results" hidden></div><div data-studio-port="model-dropdown"></div><div data-studio-port="vrm-dropdown"></div><div data-studio-port="live2d-dropdown"></div><p>Select a character above, or import the complete model package below.</p></section><section class="studio-card"><h3>Import a character</h3><div class="studio-actions" data-studio-port="imports"></div><p>PMX and Live2D need their texture folders. VRM uses a single .vrm file.</p></section><section class="studio-card"><h3>Framing & customization</h3><div data-studio-port="size"></div><div class="studio-actions" data-studio-port="framing"></div><div class="studio-actions" style="margin-top:10px"><button type="button" data-studio-action="customize">Customize model</button><button type="button" data-studio-action="expressions">Expressions & hotkeys</button></div></section></div>
 <div data-studio-content="background" hidden><section class="studio-card"><h3>Stage background</h3><div class="studio-background-colors">${['#00ff00','#168fd5','#f3edf9','#122333'].map(color=>`<button type="button" class="studio-background-swatch" data-studio-color="${color}" style="--swatch:${color}" aria-label="Set background ${color}" title="${color}"></button>`).join('')}</div><div data-studio-port="background"></div><div class="studio-actions"><button type="button" data-studio-action="transparent" aria-pressed="false">Transparent stage</button><button type="button" data-studio-action="theme">Appearance</button></div></section><section class="studio-card"><h3>Image backdrop</h3><input id="studio-background-file" type="file" accept="image/png,image/jpeg,image/webp,image/avif" aria-label="Choose a stage background image"><button type="button" id="studio-clear-image">Remove image backdrop</button><p>Image backdrops appear in window capture. Virtual Camera and Spout keep their existing output background behaviour.</p></section></div>
 <div data-studio-content="output" hidden><div data-studio-port="virtual-camera"></div><div data-studio-port="spout"></div><section class="studio-card"><h3>Voice & microphone</h3><div data-studio-port="voice"></div><div data-studio-port="voice-changer"></div><div class="studio-actions"><button type="button" data-studio-action="voice">Voice library</button><button type="button" data-studio-action="mouth">Mouth & lip sync</button><button type="button" data-studio-action="reader">Chat Reader</button></div><p>Virtual camera carries video. Route microphone or converted voice separately in your recording or call app.</p></section></div>
 <div data-studio-content="phone" hidden><div data-studio-port="phone"></div><section class="studio-card"><h3>Use your phone camera</h3><p>Open Sakura Mobile, select this PC and enter its 6-digit pairing code. Then choose Sakura Mobile in Camera & tracking.</p><div class="studio-actions"><button type="button" data-studio-action="tracking">Camera & tracking</button><button type="button" data-studio-action="send-model">Send model to mobile</button></div></section></div>
 </div></aside>
 <div id="studio-statusbar"><span class="studio-status-text" id="studio-status-text" role="status">Tracking off · choose a camera to begin</span><button id="studio-start-tracking" type="button">Start tracking</button><button id="studio-stop-tracking" type="button">Stop</button><button id="studio-calibrate" type="button">Calibrate</button><button id="studio-hands" type="button" aria-pressed="false">Hands off</button></div>
 <button id="studio-show-ui" type="button" aria-label="Show VTuber controls">Show controls</button>`;
 document.body.append(root);
 {
  const next=document.createElement('button');next.type='button';next.id='studio-new-instance';next.textContent='New instance';next.title='Open another VTuber window (up to 3)';
  byId('studio-statusbar').append(next);
  next.onclick=async()=>{next.disabled=true;try{const launch=window.pywebview?.api?.new_vtuber_instance;if(!launch)throw Error('Open the installed Sakura app to start another VTuber instance.');const result=await launch();if(result?.error)throw Error(result.error);byId('studio-status-text').textContent='Opening another VTuber instance…';}catch(error){byId('studio-status-text').textContent=error.message;}finally{next.disabled=false;}};
 }

 const backdrop=document.createElement('div');backdrop.id='studio-stage-backdrop';backdrop.setAttribute('aria-hidden','true');document.body.insertBefore(backdrop,byId('viewer'));
 const panel=byId('studio-panel'),portals=[];let active=false,currentPane='',imageUrl='',locked=false;
 try{locked=localStorage.getItem('sakura_studio_model_locked')==='true';}catch(_){}
 const nativePanels=[['tracking-modal','close-tracking-modal'],['settings-modal','close-settings-btn'],['expression-modal','close-expression-modal']];
 const click=id=>byId(id)?.click();
 const setHidden=(el,hidden)=>{if(el&&el.hidden!==hidden)el.hidden=hidden;};
 function hideNative(except=''){
  for(const [id,close] of nativePanels){const el=byId(id);if(!el||id===except||el.classList.contains('hidden'))continue;click(close);if(!el.classList.contains('hidden'))el.classList.add('hidden');}
 }
 function markPane(key){
  currentPane=key;
  for(const b of root.querySelectorAll('[data-studio-pane]'))b.setAttribute('aria-pressed',String(b.dataset.studioPane===key));
 }
 function showCustom(key){
  hideNative();setHidden(panel,false);
  for(const el of root.querySelectorAll('[data-studio-content]'))setHidden(el,el.dataset.studioContent!==key);
  byId('studio-panel-title').textContent=entries.find(e=>e[0]===key)?.[1]||key;markPane(key);
 }
 function closePanels(){hideNative();setHidden(panel,true);markPane('');}
 function nativeSettings(tab){hideNative('settings-modal');setHidden(panel,true);click('settings-btn');document.querySelector(`#settings-modal .tab-btn[data-tab="${tab}"]`)?.click();}
 function openPane(key){
  if(!active)return;
  if(key==='collab'){closePanels();click('vtuber-collab-btn');markPane(key);return;}
  if(key==='settings'){nativeSettings('general');markPane(key);return;}
  if(key==='tracking'){hideNative('tracking-modal');setHidden(panel,true);click('tracking-mode-btn');markPane(key);return;}
  if(key==='expressions'){hideNative('expression-modal');setHidden(panel,true);click('expression-editor-btn');document.querySelector('[data-model-tab="expression"]')?.click();markPane(key);return;}
  showCustom(key);
 }
 function move(node,slot){
  if(!node||!slot||portals.some(p=>p.node===node))return;
  const anchor=document.createComment('Sakura studio: restore '+(node.id||slot));node.before(anchor);portals.push({node,anchor});root.querySelector(`[data-studio-port="${slot}"]`)?.append(node);
 }
 function portControls(){
  for(const id of ['model-dropdown','vrm-dropdown','live2d-dropdown'])move(byId(id),id);
  for(const id of ['upload-pmx-toolbar','upload-vrm-toolbar','upload-live2d-toolbar','refresh-models'])move(byId(id),'imports');
  move(byId('model-size')?.closest('label'),'size');
  for(const id of ['full-model-btn','quality-btn','eye-tracking-btn','pmx-editor-btn'])move(byId(id),'framing');
  move(byId('voice-dropdown'),'voice');
  move(byId('spout-enabled')?.closest('fieldset'),'spout');
  move(byId('virtual-camera-settings-toggle')?.closest('fieldset'),'virtual-camera');
  move(byId('obs-background-enabled')?.closest('.setting-group'),'background');
  move(byId('phone-link-enabled')?.closest('fieldset'),'phone');
  move(byId('vtuber-rvc-changer-group'),'voice-changer');
 }
 function restoreControls(){for(const {node,anchor} of portals){if(anchor.parentNode)anchor.replaceWith(node);}portals.length=0;}
 function applyLock(){
  document.body.classList.toggle('studio-model-locked',active&&locked);
  byId('studio-model-lock').setAttribute('aria-pressed',String(locked));
  const label=locked?'Unlock model position':'Lock model position';
  byId('studio-model-lock').dataset.label=label;byId('studio-model-lock').title=label;byId('studio-model-lock').setAttribute('aria-label',label);
 }
 function syncMode(){
  const enabled=document.body.classList.contains('tracking-only');
  if(enabled===active)return;
  active=enabled;document.body.classList.toggle('studio-ui-active',active);setHidden(root,!active);
  for(const [id] of nativePanels)byId(id)?.classList.toggle('studio-docked',active);
  if(active){portControls();applyLock();syncStatus();if(imageUrl)document.body.classList.add('studio-image-background');}
  else{closePanels();restoreControls();document.body.classList.remove('studio-model-locked','studio-image-background');currentPane='';}
 }
 function syncStatus(){
  if(!active)return;
  const text=byId('tracking-status')?.textContent?.trim();
  if(text&&byId('studio-status-text').textContent!==text)byId('studio-status-text').textContent=text;
  const hands=byId('tracking-hands-enabled')?.getAttribute('aria-pressed')==='true';
  byId('studio-hands').textContent=hands?'Hands on':'Hands off';byId('studio-hands').setAttribute('aria-pressed',String(hands));
 }
 root.addEventListener('click',event=>{
  const nav=event.target.closest('[data-studio-pane]');if(nav){const key=nav.dataset.studioPane;if(currentPane===key&&key!=='collab')closePanels();else openPane(key);return;}
  const action=event.target.closest('[data-studio-action]')?.dataset.studioAction;
  if(action==='tracking'||action==='expressions')openPane(action);
  else if(action==='customize'||action==='mouth'){hideNative('expression-modal');setHidden(panel,true);click('expression-editor-btn');document.querySelector(`[data-model-tab="${action==='mouth'?'mouth':'coloring'}"]`)?.click();markPane('models');}
  else if(action==='voice'){nativeSettings('voice');markPane('output');}
  else if(action==='reader')openPane('tracking');
  else if(action==='send-model')click('send-model-mobile');
  else if(action==='theme'){nativeSettings('theme');markPane('background');}
  else if(action==='transparent'){
   const enabled=!document.body.classList.contains('transparent-mode');
   clearImage();const toggle=byId('obs-background-enabled');if(toggle){toggle.checked=false;toggle.dispatchEvent(new Event('change',{bubbles:true}));}
   document.body.classList.toggle('transparent-mode',enabled);document.documentElement.classList.toggle('transparent-mode',enabled);
   try{localStorage.setItem('sakura_transparency',String(enabled));}catch(_){}
   byId('bg-toggle-btn')?.setAttribute('aria-pressed',String(enabled));
   root.querySelector('[data-studio-action="transparent"]')?.setAttribute('aria-pressed',String(enabled));
   const result=window.pywebview?.api?.set_surface_transparency?.(enabled);
   if(result?.catch)result.catch(error=>{byId('studio-status-text').textContent=error.message;});
  }
  const color=event.target.closest('[data-studio-color]')?.dataset.studioColor;
  if(color){clearImage();const picker=byId('obs-background-color'),toggle=byId('obs-background-enabled');if(picker&&toggle){picker.value=color;toggle.checked=true;picker.dispatchEvent(new Event('input',{bubbles:true}));toggle.dispatchEvent(new Event('change',{bubbles:true}));}}
 });
 byId('studio-panel-close').onclick=closePanels;
 byId('studio-model-lock').onclick=()=>{locked=!locked;try{localStorage.setItem('sakura_studio_model_locked',String(locked));}catch(_){}applyLock();};
 byId('studio-hide-ui').onclick=()=>{closePanels();click('overlay-ui-btn');};
 byId('studio-show-ui').onclick=()=>click('overlay-ui-btn');
 byId('studio-start-tracking').onclick=()=>click('tracking-start');
 byId('studio-stop-tracking').onclick=()=>click('tracking-stop');
 byId('studio-calibrate').onclick=()=>click('tracking-calibrate');
 byId('studio-hands').onclick=()=>{click('tracking-hands-enabled');syncStatus();};
 // The model keeps tracking while locked; only manual pointer manipulation is blocked.
 for(const name of ['pointerdown','mousedown','touchstart','wheel','dblclick'])byId('viewer')?.addEventListener(name,event=>{
  if(active&&locked&&!(event.type==='dblclick'&&document.body.classList.contains('overlay-ui-hidden'))&&!document.body.classList.contains('model-part-picking')&&!document.body.classList.contains('picking-model-part')){event.stopImmediatePropagation();event.preventDefault();}
 },{capture:true,passive:false});
 function clearImage(){if(imageUrl)URL.revokeObjectURL(imageUrl);imageUrl='';backdrop.style.backgroundImage='';document.body.classList.remove('studio-image-background');byId('studio-background-file').value='';}
 byId('studio-clear-image').onclick=clearImage;
 byId('studio-background-file').onchange=()=>{
  const file=byId('studio-background-file').files?.[0];if(!file)return;
  if(!['image/png','image/jpeg','image/webp','image/avif'].includes(file.type)){byId('studio-status-text').textContent='Choose a PNG, JPEG, WebP or AVIF image.';return;}
  if(file.size>25*1024*1024){byId('studio-status-text').textContent='Choose a background image under 25 MB.';return;}
  if(imageUrl)URL.revokeObjectURL(imageUrl);imageUrl=URL.createObjectURL(file);backdrop.style.backgroundImage=`url("${imageUrl}")`;document.body.classList.add('studio-image-background');
 };
 // Reuse the existing expression editor's model-bound hotkeys and persistence.
 const list=byId('expression-list');
 if(list){const filter=document.createElement('input');filter.type='search';filter.id='studio-expression-search';filter.placeholder='Find an expression or shortcut…';filter.setAttribute('aria-label','Search expressions and hotkeys');list.before(filter);filter.oninput=()=>{const q=filter.value.toLocaleLowerCase();for(const item of list.children)item.hidden=!!q&&!item.textContent.toLocaleLowerCase().includes(q);};}
 const search=byId('studio-model-search'),results=byId('studio-model-results');
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
 const modeObserver=new MutationObserver(syncMode);modeObserver.observe(document.body,{attributes:true,attributeFilter:['class']});
 for(const [id] of nativePanels){const node=byId(id);if(!node)continue;new MutationObserver(()=>{
  if(!active)return;
  if(!node.classList.contains('hidden')){setHidden(panel,true);if(id==='tracking-modal')markPane('tracking');else if(id==='expression-modal')markPane('expressions');else if(id==='settings-modal')markPane('settings');}
 }).observe(node,{attributes:true,attributeFilter:['class']});}
 for(const id of ['tracking-status','tracking-hands-enabled']){const el=byId(id);if(el)new MutationObserver(syncStatus).observe(el,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:['aria-pressed']});}
 for(const id of ['tracking-connect-phone-btn','settings-connect-phone-btn','connect-phone-btn'])byId(id)?.addEventListener('click',()=>{if(active)queueMicrotask(()=>showCustom('phone'));});
 // Advanced camera settings remain the original fully wired camera/audio panel.
 const agentSection=byId('open-agent-panel')?.closest('fieldset');if(agentSection)agentSection.classList.add('studio-ai-only');
 const trackingOptions=document.querySelector('#tracking-modal .tracking-options');
 if(trackingOptions){const advanced=document.createElement('button');advanced.type='button';advanced.id='studio-tracking-advanced';advanced.textContent='Camera settings · NVIDIA / hands / smoothing';advanced.onclick=()=>{nativeSettings('audio');markPane('tracking');};trackingOptions.insertBefore(advanced,trackingOptions.firstChild);}
 document.addEventListener('keydown',event=>{if(active&&event.key==='Escape'&&!byId('vtuber-collab-dialog')?.open)closePanels();});
 window.addEventListener('pagehide',()=>{if(imageUrl)URL.revokeObjectURL(imageUrl);modeObserver.disconnect();},{once:true});
 syncMode();
 return {openPane,closePanels,isActive:()=>active};
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>installVtuberStudio(),{once:true});else installVtuberStudio();
