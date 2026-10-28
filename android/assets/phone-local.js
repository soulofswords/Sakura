import {rendererFor,openRenderer} from './avatar-channel.js';
import {wakeSettings} from './phone-wake.js';
import {modelStage} from './phone-stage.js';
import {nativeJob} from './native-jobs.js';
import {apiSetup,chooseSavedModel,transferSetup} from './local-setup.js';
import {installProviderTools} from './provider-tools.js';
const $=id=>document.getElementById(id),status=text=>$('local-status').textContent=text;
let history=[],models=[],busy=false,generation=0,callActive=false,modelReady=false,setupBusy=false;
let currentPlaces=[],placeSource='',nearbySearch=null;
wakeSettings();
const stage=modelStage({send:()=>$('local-send').click(),status,canListen:()=>modelReady&&!busy&&!callActive});
function refreshLocation(){
    if(!Sakura.locationState)return;try{const state=JSON.parse(Sakura.locationState());$('local-location').checked=!!state.enabled;$('local-location-status').textContent=state.enabled?(state.fresh?'Current area: '+state.area:'Location enabled · refreshes when you send a message'):'Location off · enable here or ask about your current location';}catch(_){}
}
window.sakuraRefreshLocation=refreshLocation;
async function setLocation(enabled){const button=$('local-location-refresh');button.disabled=true;button.setAttribute('aria-busy','true');$('local-location-status').textContent=enabled?'Getting a fresh phone location…':'Turning location off…';try{await nativeJob('setLocation',enabled);refreshLocation();}catch(error){refreshLocation();$('local-location-status').textContent=error.message;}finally{button.disabled=false;button.removeAttribute('aria-busy');}}
$('local-location').onchange=()=>setLocation($('local-location').checked);$('local-location-refresh').onclick=()=>setLocation(true);
function gate(){Sakura.setAssistantState?.(modelReady,callActive||busy);stage.gate(callActive||busy||!modelReady);for(const id of ['local-send','local-dictate'])$(id).disabled=callActive||busy||!modelReady;}
window.sakuraLocalPause=()=>{stage.stopMic();generation++;avatar()?.pause(true);};
window.sakuraPhoneNotice=text=>status(text);
window.sakuraDictation=text=>{if(!callActive){$('local-message').value=String(text).slice(0,10000);status('Check your message, then tap Send.');}};
window.sakuraCallState=active=>{callActive=active;generation++;avatar()?.stop();gate();status(active?'Call in progress · Sakura muted':'Call ended · Sakura is ready');};
try{history=JSON.parse(localStorage.getItem('sakura-local-history')||'[]').filter(m=>['user','assistant'].includes(m.role)&&typeof m.content==='string').slice(-20);}catch(_){}
function readConfig(){const data=JSON.parse(Sakura.localConfig());if(data.error)throw Error(data.error);return data;}
function renderHistory(pending=''){const box=$('local-conversation');box.replaceChildren();for(const message of history){const p=document.createElement('p');p.textContent=(message.role==='user'?'You: ':'Sakura: ')+message.content;box.append(p);}if(pending){const p=document.createElement('p');p.textContent='You: '+pending+'\nSakura is thinking…';p.dataset.pending='true';box.append(p);}else if(currentPlaces.length){
    const source=document.createElement('small');source.textContent=placeSource;box.append(source);
    for(const place of currentPlaces){const card=document.createElement('div'),name=document.createElement('p'),button=document.createElement('button');
        name.textContent=place.name+' · about '+place.distance_m+' m'+(place.address?' · '+place.address:'');button.textContent='Open in Maps';button.onclick=()=>Sakura.openPlace(place.latitude,place.longitude);card.append(name,button);box.append(card);}
}if(!pending&&nearbySearch){const button=document.createElement('button');button.textContent='Search in Maps · ratings & more results';button.onclick=()=>Sakura.searchPlaces?Sakura.searchPlaces(nearbySearch.latitude,nearbySearch.longitude,nearbySearch.query||'restaurants'):Sakura.openNearby(nearbySearch.latitude,nearbySearch.longitude);box.append(button);}box.scrollTop=box.scrollHeight;}
function store(){history=history.slice(-20);localStorage.setItem('sakura-local-history',JSON.stringify(history));localStorage.setItem('sakura-local-history-time',String(Date.now()));Sakura.syncWakeHistory?.(JSON.stringify(history));renderHistory();}
function refreshWakeHistory(){if(busy||!Sakura.wakeHistory)return;try{const data=JSON.parse(Sakura.wakeHistory());if(data.updated_at>Number(localStorage.getItem('sakura-local-history-time')||0)&&Array.isArray(data.messages)){history=data.messages.filter(m=>['user','assistant'].includes(m.role)&&typeof m.content==='string').slice(-20);localStorage.setItem('sakura-local-history',JSON.stringify(history));localStorage.setItem('sakura-local-history-time',String(data.updated_at));renderHistory();}}catch(_){}}
window.sakuraRefreshWakeHistory=refreshWakeHistory;
window.sakuraWakeCommand=text=>{if($('local-mode').classList.contains('hidden')||!modelReady||busy||callActive)return false;$('local-message').value=String(text).slice(0,10000);$('local-send').click();return true;};
function avatar(){return rendererFor($('local-avatar'));}
async function readyAvatar(){return openRenderer($('local-avatar'));}
async function loadSelected(){const entry=models.find(m=>m.id===$('local-models').value);modelReady=false;stage.loaded(false);gate();if(!entry)return;status('Loading '+entry.name+'…');try{const view=await readyAvatar();await view.load(entry.url.split('/').map(encodeURIComponent).join('/'));localStorage.setItem('sakura-local-model',entry.id);modelReady=true;stage.loaded(true);status(entry.name+' · '+entry.format.toUpperCase());}catch(error){status(error.message);}finally{gate();}}
function catalog(selected){models=JSON.parse(Sakura.localModels());const options=models.filter(m=>m.format===$('local-format').value);$('local-models').replaceChildren(...options.map(m=>{const option=document.createElement('option');option.value=m.id;option.textContent=m.name;return option;}));if(options.some(m=>m.id===selected))$('local-models').value=selected;}
const config=readConfig();$('local-provider').value=config.provider;$('local-model-id').value=config.model;$('local-voice').value=config.voice;$('local-address').value=config.address;$('local-news-area').value=config.news_area||'';
$('local-news-area').onchange=()=>{try{const data=JSON.parse(Sakura.setNewsArea($('local-news-area').value.trim()));if(data.error)throw Error(data.error);$('local-news-area').value=data.news_area;status('News area saved · '+(data.news_area||'India'));}catch(error){status(error.message);}};
$('local-key').placeholder=config.key_set?'Saved securely · leave blank to keep':'Enter your API key';
$('local-provider').onchange=()=>{$('local-model-id').value=$('local-provider').value==='gemini'?'gemini-flash-latest':'gpt-4.1-mini';};
$('local-save').onclick=()=>{try{const data=JSON.parse(Sakura.configureLocal($('local-provider').value,$('local-key').value.trim(),$('local-model-id').value.trim(),$('local-voice').value,$('local-address').value));if(data.error)throw Error(data.error);$('local-key').value='';$('local-key').placeholder=data.key_set?'Saved securely · leave blank to keep':'Enter your API key';generation++;avatar()?.stop();status('Saved · '+(data.voice==='male'?'Male':'Female')+' voice');}catch(error){status(error.message);}};
// Voice changes are applied immediately, including when a key has already been saved.
$('local-voice').onchange=()=>$('local-save').click();
$('local-address').onchange=()=>{try{const data=JSON.parse(Sakura.setHonorific($('local-address').value));if(data.error)throw Error(data.error);generation++;avatar()?.stop();$('local-address').value=data.address;status('Saved · '+({sir:'Sir',maam:'Ma’am',none:'No title'}[data.address]));}catch(error){$('local-address').value=readConfig().address;status(error.message);}};
const providerTools=document.createElement('div');$('local-save').after(providerTools);
installProviderTools(providerTools,{provider:$('local-provider'),key:$('local-key'),model:$('local-model-id'),voice:$('local-voice'),address:$('local-address'),status,onSaved(){generation++;avatar()?.stop();}});
$('local-format').onchange=()=>catalog();$('local-models').onchange=loadSelected;
async function activateModel(model){$('local-format').value=model.format;catalog(model.id);await loadSelected();}
async function setup(add=false){
    if(setupBusy)return;setupBusy=true;
    try{
        const saved=JSON.parse(Sakura.localModels());
        if(!saved.length){const config=await apiSetup();if(!config){status('Setup cancelled. Local needs at least one saved model.');return;}$('local-provider').value=config.provider;$('local-model-id').value=config.model;$('local-voice').value=config.voice;$('local-key').placeholder='Saved securely · leave blank to keep';}
        const choice=add||!saved.length?{add:true}:await chooseSavedModel();if(!choice)return;
        const model=choice.add?await transferSetup():choice.model;if(model)await activateModel(model);
        else if(!modelReady)status('Add a model to finish Local setup.');
    }catch(error){status(error.message);}finally{setupBusy=false;gate();}
}
$('local-receive').onclick=()=>setup(true);$('local-choose-model').onclick=()=>setup();
$('local-send').onclick=async()=>{
    const text=$('local-message').value.trim();if(!text||busy||callActive||!modelReady)return;
    busy=true;Sakura.setAssistantState?.(modelReady,true);stage.gate(true);currentPlaces=[];placeSource='';nearbySearch=null;$('local-send').disabled=true;$('local-send').setAttribute('aria-busy','true');$('local-send').textContent='Sending…';const current=++generation;avatar()?.stop();renderHistory(text);
    const next=[...history,{role:'user',content:text}].slice(-19);status('Sakura is thinking…');
    try{
        const data=await nativeJob('localChat',JSON.stringify(next));if(current!==generation)return;
        const answer=String(data.reply||'').trim();if(!answer)throw Error('No reply was returned. Try another model or check the provider quota.');
        currentPlaces=(data.places||[]).filter(p=>typeof p.name==='string'&&Number.isFinite(p.latitude)&&Number.isFinite(p.longitude)).slice(0,5);placeSource=data.source||'';
        nearbySearch=data.maps_search&&Number.isFinite(data.maps_search.latitude)&&Number.isFinite(data.maps_search.longitude)?data.maps_search:null;
        history=[...next,{role:'assistant',content:answer}];store();$('local-message').value='';status('Reply ready');
        if($('local-speech').checked){
            $('local-send').textContent='Loading voice…';
            status('Loading '+readConfig().voice+' voice…');
            try{const result=await nativeJob('localSpeak',answer);if(current!==generation)return;const view=await readyAvatar();status('Speaking');$('local-send').textContent='Speaking…';await view.speak(result.audio);if(current===generation)status('Ready');}
            catch(error){if(current===generation)status('Voice unavailable: '+error.message+' Your text reply is still available.');}
        }
    }catch(error){if(current===generation){status('Message failed: '+error.message);renderHistory();}}finally{busy=false;$('local-send').removeAttribute('aria-busy');$('local-send').textContent='Send';gate();refreshLocation();}
};
$('local-stop').onclick=()=>{generation++;avatar()?.stop();status('Stopped');};
$('local-dictate').onclick=()=>{if(!callActive&&!busy)Sakura.dictate();};
$('local-clear').onclick=()=>{generation++;avatar()?.stop();history=[];currentPlaces=[];placeSource='';nearbySearch=null;store();status('Conversation cleared');};
window.sakuraLocalVisible=async visible=>{
    if(!visible){modelReady=false;stage.exit();gate();generation++;avatar()?.stop();$('local-avatar').src='about:blank';return;}
    // Recreate the iframe after leaving Local mode so hidden render loops do not use the GPU.
    $('local-avatar').removeAttribute('src');
    modelReady=false;gate();await setup();
};
window.addEventListener('pagehide',()=>{stage.stopMic();generation++;avatar()?.stop();});
refreshWakeHistory();renderHistory();catalog(localStorage.getItem('sakura-local-model'));gate();refreshLocation();
