import {nativeJob} from './native-jobs.js';
import {apiSetup,chooseSavedModel,transferSetup} from './local-setup.js';
import {installProviderTools} from './provider-tools.js';
const $=id=>document.getElementById(id),status=text=>$('local-status').textContent=text;
let history=[],models=[],busy=false,generation=0,callActive=false,modelReady=false,setupBusy=false;
function gate(){for(const id of ['local-send','local-dictate'])$(id).disabled=callActive||busy||!modelReady;}
window.sakuraLocalPause=()=>{generation++;avatar()?.stop();};
window.sakuraPhoneNotice=text=>status(text);
window.sakuraDictation=text=>{if(!callActive){$('local-message').value=String(text).slice(0,10000);status('Check your message, then tap Send.');}};
window.sakuraCallState=active=>{callActive=active;generation++;avatar()?.stop();gate();status(active?'Call in progress · Sakura muted':'Call ended · Sakura is ready');};
try{history=JSON.parse(localStorage.getItem('sakura-local-history')||'[]').filter(m=>['user','assistant'].includes(m.role)&&typeof m.content==='string').slice(-20);}catch(_){}
function readConfig(){const data=JSON.parse(Sakura.localConfig());if(data.error)throw Error(data.error);return data;}
function renderHistory(pending=''){const box=$('local-conversation');box.replaceChildren();for(const message of history){const p=document.createElement('p');p.textContent=(message.role==='user'?'You: ':'Sakura: ')+message.content;box.append(p);}if(pending){const p=document.createElement('p');p.textContent='You: '+pending+'\nSakura is thinking…';p.dataset.pending='true';box.append(p);}box.scrollTop=box.scrollHeight;}
function store(){history=history.slice(-20);localStorage.setItem('sakura-local-history',JSON.stringify(history));renderHistory();}
function avatar(){return $('local-avatar').contentWindow?.phoneAvatar;}
async function readyAvatar(){
    if(!$('local-avatar').getAttribute('src'))$('local-avatar').src='/local-viewer.html';
    const start=Date.now();while(!avatar()){
        if($('local-avatar').contentWindow?.phoneAvatarError)throw Error($('local-avatar').contentWindow.phoneAvatarError);
        if(Date.now()-start>30000)throw Error('Model renderer did not start. Update Android System WebView.');
        await new Promise(resolve=>setTimeout(resolve,100));
    }return avatar();
}
async function loadSelected(){const entry=models.find(m=>m.id===$('local-models').value);modelReady=false;gate();if(!entry)return;status('Loading '+entry.name+'…');try{const view=await readyAvatar();await view.load(entry.url.split('/').map(encodeURIComponent).join('/'));localStorage.setItem('sakura-local-model',entry.id);modelReady=true;status(entry.name+' · '+entry.format.toUpperCase());}catch(error){status(error.message);}finally{gate();}}
function catalog(selected){models=JSON.parse(Sakura.localModels());const options=models.filter(m=>m.format===$('local-format').value);$('local-models').replaceChildren(...options.map(m=>{const option=document.createElement('option');option.value=m.id;option.textContent=m.name;return option;}));if(options.some(m=>m.id===selected))$('local-models').value=selected;}
const config=readConfig();$('local-provider').value=config.provider;$('local-model-id').value=config.model;$('local-voice').value=config.voice;$('local-address').value=config.address;
$('local-key').placeholder=config.key_set?'Saved securely · leave blank to keep':'Enter your API key';
$('local-provider').onchange=()=>{$('local-model-id').value=$('local-provider').value==='gemini'?'gemini-flash-latest':'gpt-4.1-mini';};
$('local-save').onclick=()=>{try{const data=JSON.parse(Sakura.configureLocal($('local-provider').value,$('local-key').value.trim(),$('local-model-id').value.trim(),$('local-voice').value,$('local-address').value));if(data.error)throw Error(data.error);$('local-key').value='';$('local-key').placeholder=data.key_set?'Saved securely · leave blank to keep':'Enter your API key';generation++;avatar()?.stop();status('Saved · '+(data.voice==='male'?'Male':'Female')+' voice');}catch(error){status(error.message);}};
// Voice changes are applied immediately, including when a key has already been saved.
$('local-voice').onchange=()=>$('local-save').click();
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
    busy=true;$('local-send').disabled=true;$('local-send').setAttribute('aria-busy','true');$('local-send').textContent='Sending…';const current=++generation;avatar()?.stop();renderHistory(text);
    const next=[...history,{role:'user',content:text}].slice(-19);status('Sakura is thinking…');
    try{
        const data=await nativeJob('localChat',JSON.stringify(next));if(current!==generation)return;
        const answer=String(data.reply||'').trim();if(!answer)throw Error('No reply was returned. Try another model or check the provider quota.');
        history=[...next,{role:'assistant',content:answer}];store();$('local-message').value='';status('Reply ready');
        if($('local-speech').checked){
            $('local-send').textContent='Loading voice…';
            status('Loading '+readConfig().voice+' voice…');
            try{const result=await nativeJob('localSpeak',answer);if(current!==generation)return;const view=await readyAvatar();status('Speaking');$('local-send').textContent='Speaking…';await view.speak(result.audio);if(current===generation)status('Ready');}
            catch(error){if(current===generation)status('Voice unavailable: '+error.message+' Your text reply is still available.');}
        }
    }catch(error){if(current===generation){status('Message failed: '+error.message);renderHistory();}}finally{busy=false;$('local-send').removeAttribute('aria-busy');$('local-send').textContent='Send';gate();}
};
$('local-stop').onclick=()=>{generation++;avatar()?.stop();status('Stopped');};
$('local-dictate').onclick=()=>{if(!callActive&&!busy)Sakura.dictate();};
$('local-clear').onclick=()=>{generation++;avatar()?.stop();history=[];store();status('Conversation cleared');};
window.sakuraLocalVisible=async visible=>{
    if(!visible){generation++;avatar()?.stop();$('local-avatar').src='about:blank';return;}
    // Recreate the iframe after leaving Local mode so hidden render loops do not use the GPU.
    $('local-avatar').removeAttribute('src');
    modelReady=false;gate();await setup();
};
window.addEventListener('pagehide',()=>{generation++;avatar()?.stop();});
renderHistory();catalog(localStorage.getItem('sakura-local-model'));gate();
