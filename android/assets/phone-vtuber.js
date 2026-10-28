import {rendererFor,openRenderer} from './avatar-channel.js';
import {nativeJob} from './native-jobs.js';
const $=id=>document.getElementById(id);
const panel=document.createElement('main');panel.id='phone-vtuber-mode';panel.className='hidden';
panel.innerHTML='<section><h2>VTuber · on this phone</h2><p>Load a model and animate it with this phone’s camera. No PC or AI key required.</p><button id="phone-model-import">Import model from phone</button><button id="phone-model-pc">Import model from paired PC</button><small>VRM: choose its file. PMX or Live2D: choose a ZIP containing one complete model and its textures. Large models may exceed your phone’s memory.</small><label for="phone-model-list">Saved models</label><select id="phone-model-list"></select><button id="phone-model-load">Load selected model</button></section><iframe id="phone-tracking-avatar" title="Phone VTuber model" allow="camera" sandbox="allow-scripts allow-same-origin" style="width:100%;height:55vh;border:0;border-radius:16px"></iframe><section><label for="phone-local-facing">Tracking camera</label><select id="phone-local-facing"><option value="user">Front camera</option><option value="environment">Rear camera</option></select><label><input id="phone-local-hands" type="checkbox" style="width:auto"> Track hands and fingers</label><button id="phone-local-tracking" aria-pressed="false">Start tracking</button><button id="phone-local-calibrate">Calibrate neutral pose</button><p id="phone-local-tracking-status" role="status">Import or select a model to begin.</p><small>Camera frames stay on this phone. Tracking stops when you leave this mode or put Sakura in the background.</small></section>';
document.body.insertBefore(panel,$('pc-mode'));
const button=document.createElement('button');button.id='mode-phone-vtuber';button.innerHTML='<b>VTuber · on this phone</b><br><small>Import a model and track your face and hands without a PC.</small>';$('app-modes').append(button);
let models=[],ready=false,running=false,revision=0;
const status=text=>$('phone-local-tracking-status').textContent=text;
const api=()=>rendererFor($('phone-tracking-avatar'));
function catalog(selected){models=JSON.parse(Sakura.localModels());$('phone-model-list').replaceChildren(...models.map(model=>new Option(model.name+' · '+model.format.toUpperCase(),model.id)));if(selected)$('phone-model-list').value=selected;}
async function avatar(){return openRenderer($('phone-tracking-avatar'));}
function stop(){revision++;api()?.stopTracking();running=false;$('phone-local-tracking').textContent='Start tracking';$('phone-local-tracking').setAttribute('aria-pressed','false');}
window.sakuraStopLocalTracking=()=>{stop();if(!panel.classList.contains('hidden'))status('Tracking stopped. Tap Start tracking to resume.');};
async function load(){stop();ready=false;const model=models.find(m=>m.id===$('phone-model-list').value);if(!model){status('Import a model first.');return;}status('Loading '+model.name+'…');try{const view=await avatar();view.pause(false);await view.load(model.url.split('/').map(encodeURIComponent).join('/'));ready=true;status(model.name+' ready. Start tracking when you want to use the camera.');}catch(error){status(error.message);}}
button.onclick=()=>{window.stopPhoneTracking?.();window.stopPhoneVision?.();window.sakuraLocalVisible?.(false);$('app-modes').classList.add('hidden');$('pc-mode').classList.add('hidden');$('local-mode').classList.add('hidden');$('change-mode').classList.remove('hidden');panel.classList.remove('hidden');try{catalog();}catch(error){status(error.message);}};
$('change-mode').addEventListener('click',()=>{stop();panel.classList.add('hidden');api()?.pause(true);});
$('phone-model-import').onclick=async()=>{const b=$('phone-model-import');b.disabled=true;stop();try{const model=await nativeJob('importPhoneModel');catalog(model.id);await load();}catch(error){status(error.message);}finally{b.disabled=false;}};
$('phone-model-load').onclick=load;
$('phone-local-tracking').onclick=async()=>{if(running){stop();status('Tracking off.');return;}if(!ready){status('Load a model first.');return;}const generation=++revision;const b=$('phone-local-tracking');b.disabled=true;try{api()?.pause(false);await api().startTracking($('phone-local-facing').value,$('phone-local-hands').checked);if(generation!==revision){api()?.stopTracking();return;}running=true;b.textContent='Stop tracking';b.setAttribute('aria-pressed','true');status('Tracking on · camera video stays on this phone.');}catch(error){stop();status(error.message);}finally{b.disabled=false;}};
$('phone-local-calibrate').onclick=()=>{if(running)api()?.calibrate();else status('Start tracking before calibration.');};
$('phone-local-hands').onchange=()=>api()?.hands($('phone-local-hands').checked);
$('phone-local-facing').onchange=()=>{stop();status('Camera changed. Tap Start tracking to use it.');};
document.addEventListener('visibilitychange',()=>{if(document.hidden)window.sakuraStopLocalTracking();});

$('phone-model-pc').onclick=async()=>{
 const button=$('phone-model-pc');button.disabled=true;stop();let requestId='';
 try{
  status('Connecting to your paired PC…');await window.sakuraEnsurePc();
  const request=await nativeJob('requestModelTransfer');requestId=request.request_id;
  const deadline=Date.now()+600000;
  while(!panel.classList.contains('hidden')&&Date.now()<deadline){
   status('Choose a model in the PC popup, then send it to this phone.');
   const state=await nativeJob('phoneState'),transfer=state.transfer_request;
   if(!transfer||transfer.id!==requestId)throw Error('The PC model request expired. Try again.');
   if(['failed','cancelled'].includes(transfer.status))throw Error(transfer.error||'PC model selection cancelled.');
   if(transfer.status==='ready'){status('Saving the complete model on this phone…');const model=await nativeJob('receiveModel',requestId);requestId='';catalog(model.id);await load();return;}
   await new Promise(resolve=>setTimeout(resolve,1000));
  }
  throw Error('Model transfer cancelled or timed out.');
 }catch(error){status(error.message);}finally{if(requestId)void nativeJob('cancelModelTransfer',requestId).catch(()=>{});button.disabled=false;}
};
