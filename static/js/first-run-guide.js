/* A local, optional tour. Navigation never grants a permission or runs a tool. */
const mobile=!!document.getElementById('app-modes');
const agent=/agent/i.test(document.title)&&!mobile;
const edition=mobile?'mobile':agent?'agent':window.SAKURA_EDITION==='vtuber'?'vtuber':'companion';
const key='sakura-setup-guide-v1-'+edition;
const click=selector=>document.querySelector(selector)?.click();
const openDock=selector=>{const button=document.querySelector(selector);if(button?.getAttribute('aria-pressed')!=='true')button?.click();};
const openSettings=()=>{const dock=edition==='vtuber'?'[data-studio-pane="settings"]':'[data-companion-pane="settings"]';if(document.querySelector(dock))openDock(dock);else{const panel=document.getElementById('settings-modal');if(!panel||getComputedStyle(panel).display==='none'||panel.classList.contains('hidden'))click('#settings-btn');}click('#settings-modal [data-tab="general"]');};
const phoneMode=(button,panel)=>{if(document.getElementById(panel)&&!document.getElementById(panel).classList.contains('hidden'))return;if(document.getElementById('app-modes')?.classList.contains('hidden'))click('#change-mode');click(button);};
const mobileLocal=()=>{phoneMode('#mode-local','local-mode');if(document.body.classList.contains('local-model-fullscreen')&&!document.getElementById('local-stage-panel')?.classList.contains('stage-panel-open'))click('#local-panel-toggle');const settings=document.getElementById('phone-settings');if(settings)settings.open=true;};
const agentTasks=()=>click('#agent-studio-nav button[aria-label="Tasks"]');
const steps=mobile?[
 ['Welcome to Sakura','Use your character on this phone, or connect to Sakura on your PC. You can change this later.'],
 ['Choose how to use it','“Use on this phone” opens your character and chat. “Connect to PC” uses your phone as a camera and remote. “VTuber · on this phone” runs character tracking without an AI key.'],
 ['Connect to your PC','Keep both devices on the same Wi-Fi. Search for your PC, then enter its pairing code. For first pairing, verify the certificate fingerprint shown by Sakura on the PC.','Show PC connection',()=>phoneMode('#mode-pc','pc-mode')],
 ['Add a character','Open Settings & characters, choose Live2D, PMX or VRM, then choose a saved character or add one from your PC. Keep the model’s textures with it.','Show character settings',()=>{mobileLocal();document.getElementById('local-format')?.scrollIntoView({block:'center'});}],
 ['Set up chat and voice','For phone chat, choose an AI provider and enter your own key under AI & voice. Save your settings. Camera, location and hands-free listening are optional.','Show AI & voice',()=>{mobileLocal();document.getElementById('local-provider')?.scrollIntoView({block:'center'});}],
 ['Ready when you are','Tap the microphone to speak, or type a message. Start camera tracking only when you want it. Reopen this guide from Appearance → Setup guide.']
]:agent?[
 ['Meet Sakura Agent','Chat normally, or describe a task you want Sakura to complete. A task can use files and connected apps.'],
 ['Choose your AI','Use the model selector beside the message box. Configure a provider or local model in Local AI if needed. Your selected model answers and plans the task.','Show model selector',()=>{agentTasks();const options=document.getElementById('agent-task-options');if(options)options.open=true;const el=document.getElementById('planner-provider');el?.scrollIntoView({block:'center'});el?.focus();}],
 ['Choose the right folder','Open Task settings and select the workspace for file tasks. Review the goal and the selected skills before starting.','Show Task settings',()=>{agentTasks();const el=document.getElementById('agent-task-options');if(el)el.open=true;document.getElementById('workspace')?.focus();}],
 ['Review actions','Read the proposed action and its arguments before approving. Approval settings control which actions can run automatically. You can reject, pause or cancel work.'],
 ['Connect only what you need','Add an MCP service in Connections when a task requires it. Sign in through the provider’s setup. Reopen this guide from Task history → Agent telemetry → Setup guide.','Show Connections',()=>{click('#agent-studio-nav button[aria-label="Connections"]');document.getElementById('connections')?.scrollIntoView({block:'start'});}]
]:[
 ['Welcome to '+(edition==='vtuber'?'Sakura VTuber':'Sakura Companion'),edition==='vtuber'?'Bring your character to life with camera tracking, expressions and streaming tools.':'Chat with your character, switch to VTuber tracking, or use Agent mode for tasks.'],
 ['Choose your character','Open Models on the left. Choose a saved PMX, VRM or Live2D model, or import a complete model package. Cloud import asks you to sign in only when you use it.','Show Models',()=>openDock(edition==='vtuber'?'[data-studio-pane="models"]':'[data-companion-pane="character"]')],
 ...(edition==='vtuber'?[]:[['Choose chat and voice','Open the speaker icon for Voice & speech. Friend is for conversation; Teacher supports practical work. Choose your AI provider or local model in Settings.','Show Voice & speech',()=>openDock('[data-companion-pane="voice"]')]]),
 ['Camera is optional','Open Camera & tracking to choose a webcam or Sakura Mobile. Start tracking when ready, then look straight ahead and calibrate. You can toggle hand tracking separately.','Show Camera & tracking',()=>openDock(edition==='vtuber'?'[data-studio-pane="tracking"]':'[data-companion-pane="camera"]')],
 ['Make it yours','Use Model Settings to adjust your character and Background for your stage. Streaming & output contains Virtual Camera and Spout. Reopen this guide from Settings → General.','Show Settings',openSettings]
];
const style=document.createElement('style');
style.textContent=`
#sakura-setup-guide{box-sizing:border-box;position:fixed;inset:auto;margin:0;z-index:1900;width:min(420px,calc(100vw - 28px));max-height:calc(100dvh - 28px);overflow:auto;border:1px solid var(--ui-line,var(--mobile-border,#414b59));border-radius:20px;padding:22px;background:var(--ui-card,var(--mobile-card,var(--ag-card,#20242b)));color:var(--ui-ink,var(--mobile-text,var(--ag-ink,#edf1f7)));font:15px/1.6 system-ui;box-shadow:0 12px 36px #0004;-webkit-app-region:no-drag}
#sakura-setup-guide:not([open]){display:none!important}
#sakura-setup-guide h2{font-size:22px;line-height:1.3;margin:12px 0;color:inherit}
#sakura-setup-guide p{color:inherit;margin:12px 0}
#sakura-setup-guide .setup-progress{font-size:12px;opacity:.75}
#sakura-setup-guide button{font:inherit;border:1px solid var(--ui-line,var(--mobile-border,#657080));border-radius:10px;padding:10px 13px;min-height:44px;width:auto;background:var(--ui-button,var(--mobile-button,#303c4b));color:inherit;cursor:pointer;-webkit-app-region:no-drag}
#sakura-setup-guide button[hidden],#sakura-setup-focus[hidden]{display:none!important}
#sakura-setup-guide button:disabled{opacity:.45;cursor:default}
#sakura-setup-guide button:focus-visible{outline:2px solid var(--ui-accent,var(--mobile-accent,#91ceff));outline-offset:3px}
#sakura-setup-guide .setup-actions{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;margin-top:16px}
#sakura-setup-guide .setup-next{background:#147caf;color:white;border-color:#147caf}
#sakura-setup-guide .setup-show{width:100%;margin-top:6px}
#sakura-setup-guide .setup-steps{display:flex;gap:7px;margin:13px 0 8px}
#sakura-setup-guide .setup-step{flex:1;padding:0;min-height:32px;font-size:12px}
#sakura-setup-guide .setup-step[aria-current=step]{background:#147caf;border-color:#147caf;color:white}
#sakura-setup-guide .setup-hint{font-size:12px;line-height:1.5;color:var(--ui-muted,var(--mobile-muted,#b4c5d2));margin-bottom:0}
#sakura-setup-focus{box-sizing:border-box;position:fixed;pointer-events:none;z-index:1899;border:3px solid #58c8eb;border-radius:12px;box-shadow:0 0 0 3px #10232c;}
`;
document.head.append(style);
const dialog=document.createElement('dialog');dialog.id='sakura-setup-guide';dialog.setAttribute('aria-labelledby','sakura-setup-title');dialog.setAttribute('aria-modal','false');
dialog.innerHTML='<div class="setup-progress" aria-live="polite"></div><nav class="setup-steps" aria-label="Setup steps"></nav><h2 id="sakura-setup-title"></h2><p class="setup-description"></p><button type="button" class="setup-show" hidden></button><p class="setup-hint" role="status">Explore at your pace. You can skip setup and reopen it later.</p><div class="setup-actions"><button type="button" class="setup-skip">Skip setup</button><button type="button" class="setup-back">Back</button><button type="button" class="setup-next">Next</button></div>';
document.body.append(dialog);
const ring=document.createElement('div');ring.id='sakura-setup-focus';ring.hidden=true;ring.setAttribute('aria-hidden','true');document.body.append(ring);
let state={step:0,done:false,seen:false};try{const saved=JSON.parse(localStorage.getItem(key)||'null');if(saved&&Number.isInteger(saved.step)&&saved.step>=0&&saved.step<steps.length)state={step:saved.step,done:saved.done===true,seen:saved.seen===true||saved.done===true};}catch{}
const nativeGuide=()=>{try{return window.pywebview?.api||window.parent?.pywebview?.api;}catch{return null;}};
let target=null,layoutFrame=0,navigationTicket=0;
const save=()=>{try{localStorage.setItem(key,JSON.stringify(state));}catch{}};
const visible=el=>!!el&&el.getBoundingClientRect().width>0&&el.getBoundingClientRect().height>0&&getComputedStyle(el).visibility!=='hidden'&&getComputedStyle(el).display!=='none';
function targetForStep(){
 const label=steps[state.step][2]||'';
 if(label==='Show Settings')return document.querySelector(edition==='vtuber'?'[data-studio-pane="settings"]':'[data-companion-pane="settings"]')||document.getElementById('settings-btn');
 const selector=mobile?({'Show PC connection':'#pc-mode','Show character settings':'#local-format','Show AI & voice':'#local-provider'}[label]):agent?({'Show model selector':'#planner-provider','Show Task settings':'#workspace','Show Connections':'#connections'}[label]):({'Show Models':edition==='vtuber'?'[data-studio-pane="models"]':'[data-companion-pane="character"]','Show Voice & speech':'[data-companion-pane="voice"]','Show Camera & tracking':edition==='vtuber'?'[data-studio-pane="tracking"]':'[data-companion-pane="camera"]','Show Settings':'#settings-btn'}[label]);
 return selector?document.querySelector(selector):null;
}
function layout(){
 layoutFrame=0;if(!dialog.open)return;
 const w=innerWidth,h=innerHeight,rect=dialog.getBoundingClientRect();
 let x=Math.max(14,(w-rect.width)/2),y=Math.max(14,(h-rect.height)/2);
 if(visible(target)){
  const t=target.getBoundingClientRect();
  Object.assign(ring.style,{left:Math.max(2,t.left-5)+'px',top:Math.max(2,t.top-5)+'px',width:Math.max(0,Math.min(w-4,t.right+5)-Math.max(2,t.left-5))+'px',height:Math.max(0,Math.min(h-4,t.bottom+5)-Math.max(2,t.top-5))+'px'});ring.hidden=false;
  // Keep the app usable: prefer beside the target, then below/above it.
  if(t.right+20+rect.width<=w-14){x=t.right+20;y=Math.max(14,Math.min(t.top,h-rect.height-14));}
  else if(t.left-20-rect.width>=14){x=t.left-20-rect.width;y=Math.max(14,Math.min(t.top,h-rect.height-14));}
  else if(t.bottom+20+rect.height<=h-14)y=t.bottom+20;
  else if(t.top-20-rect.height>=14)y=t.top-20-rect.height;
  else y=t.top<h/2?Math.max(14,h-rect.height-14):14;
 }else ring.hidden=true;
 dialog.style.left=Math.max(14,Math.min(x,w-rect.width-14))+'px';dialog.style.top=Math.max(14,Math.min(y,h-rect.height-14))+'px';
}
const scheduleLayout=()=>{if(dialog.open&&!layoutFrame)layoutFrame=requestAnimationFrame(layout);};
const resetFocus=()=>{navigationTicket++;target=null;ring.hidden=true;};
function go(step){resetFocus();state.step=step;save();render();void showStep();}
function render(){
 const [title,body,label]=steps[state.step];dialog.querySelector('h2').textContent=title;dialog.querySelector('.setup-description').textContent=body;dialog.querySelector('.setup-progress').textContent='Quick setup · '+(state.step+1)+' of '+steps.length;
 const show=dialog.querySelector('.setup-show');show.hidden=!label;show.textContent=label||'';
 dialog.querySelector('.setup-back').disabled=state.step===0;dialog.querySelector('.setup-next').textContent=state.step===steps.length-1?'Finish':'Next';
 dialog.querySelector('.setup-hint').textContent='Next opens the matching panel automatically. The guide stays open while you try the controls.';
 const nav=dialog.querySelector('.setup-steps');nav.replaceChildren();
 steps.forEach(([name],i)=>{const b=document.createElement('button');b.type='button';b.className='setup-step';b.textContent=String(i+1);b.setAttribute('aria-label','Step '+(i+1)+': '+name);if(i===state.step)b.setAttribute('aria-current','step');b.onclick=()=>go(i);nav.append(b);});
 scheduleLayout();
}
function open(){state.seen=true;save();if(!mobile)void nativeGuide()?.setup_guide_seen?.(edition,true)?.catch(()=>{});resetFocus();render();if(!dialog.open)dialog.show();layout();dialog.querySelector('.setup-next').focus({preventScroll:true});}
function finish(){resetFocus();state.done=true;save();dialog.close();}
dialog.querySelector('.setup-next').onclick=()=>state.step===steps.length-1?finish():go(state.step+1);
dialog.querySelector('.setup-back').onclick=()=>{if(state.step>0)go(state.step-1);};
dialog.querySelector('.setup-skip').onclick=finish;
dialog.addEventListener('cancel',event=>{event.preventDefault();finish();});
dialog.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();finish();}});
async function showStep(){
 const ticket=++navigationTicket;
 if(!steps[state.step][3]){scheduleLayout();return;}
 try{
  await steps[state.step][3]?.();
  if(ticket!==navigationTicket||!dialog.open)return;
  target=targetForStep();
  dialog.querySelector('.setup-hint').textContent=visible(target)?'Highlighted above or beside this guide. Try the controls, then choose Next.':'The panel was requested. If it is still loading, wait a moment or open it from the toolbar.';
  layout();requestAnimationFrame(()=>{if(ticket===navigationTicket)scheduleLayout();});
 }catch{if(ticket===navigationTicket&&dialog.open)dialog.querySelector('.setup-hint').textContent='This control is not ready yet. You can open it from the toolbar or continue setup.';}
}
dialog.querySelector('.setup-show').onclick=showStep;
window.addEventListener('resize',scheduleLayout);window.addEventListener('scroll',scheduleLayout,true);
window.sakuraOpenSetupGuide=()=>{state={step:0,done:false,seen:true};save();open();};
const help=document.createElement('button');help.type='button';help.id='sakura-reopen-setup';help.textContent='Setup guide';help.onclick=window.sakuraOpenSetupGuide;
function mountHelp(){const target=mobile?document.getElementById('mobile-appearance-home'):agent?document.getElementById('agent-metrics'):document.getElementById('tab-general');if(target&&!help.isConnected)target.append(help);if(mobile){const panel=document.querySelector('#local-stage-panel .mobile-appearance');if(panel&&!panel.querySelector('[data-setup-reopen]')){const button=help.cloneNode(true);button.removeAttribute('id');button.dataset.setupReopen='';button.onclick=window.sakuraOpenSetupGuide;panel.append(button);}}}
mountHelp();
let attempts=0;
const ready=setInterval(async()=>{mountHelp();const splash=document.getElementById('startup-render-status');if(splash&&visible(splash)&&attempts++<120)return;clearInterval(ready);
 if(!mobile&&!state.seen){try{const api=nativeGuide();if(api?.setup_guide_seen){const known=await Promise.race([api.setup_guide_seen(edition,false),new Promise(resolve=>setTimeout(()=>resolve(false),1500))]);if(known===true){state.seen=true;save();}}}catch{}}
 if(!state.seen&&!state.done)open();},250);
window.addEventListener('pagehide',()=>{clearInterval(ready);if(layoutFrame)cancelAnimationFrame(layoutFrame);navigationTicket++;},{once:true});
