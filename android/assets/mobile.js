import AvatarTracking from '/static/js/avatar-tracking.js';
import {installButtonFeedback} from '/static/js/button-feedback.js';
installButtonFeedback();
import {nativeJob} from './native-jobs.js';
const $=id=>document.getElementById(id),status=message=>$('status').textContent=message;
let connected=false,remoteTracking=false,frameBusy=false,expressions=[],active=new Set();
let localMode=false,reconnecting=null,manualDisconnect=false,retryTimer=null,retryDelay=2000;
const standaloneAvailable=Boolean(Sakura.localAvailable?.());
let selectedMode=standaloneAvailable?null:'pc';
async function reconnect(address){
    if(reconnecting)return reconnecting;
    reconnecting=(async()=>{try{const data=await nativeJob('reconnectAsync',address);connectedPc(data);retryDelay=2000;localStorage.setItem('sakura-last-pc',address);return data;}finally{reconnecting=null;}})();return reconnecting;
}
function savedComputers(){try{return JSON.parse(Sakura.remembered());}catch(_){return [];}}
async function autoReconnect(forTransfer=false){
    clearTimeout(retryTimer);if((selectedMode!=='pc'&&!forTransfer)||manualDisconnect||connected||reconnecting)return;
    const computers=savedComputers(),last=localStorage.getItem('sakura-last-pc');const pc=computers.find(p=>p.address===last)||computers.at(-1);if(!pc)return;
    try{await reconnect(pc.address);}catch(error){status('PC not available yet. Saved pairing kept; retrying automatically. '+error.message);retryTimer=setTimeout(autoReconnect,retryDelay);retryDelay=Math.min(30000,retryDelay*2);}
}
window.sakuraEnsurePc=async()=>{if(connected)return;manualDisconnect=false;await autoReconnect(true);if(!connected)throw Error('Open the paired PC app for this one-time model transfer. Existing phone models and Local chat do not require the PC.');};
window.sakuraResume=()=>{window.sakuraLocalPause?.();autoReconnect();};
let localModule;
async function selectMode(local){
    selectedMode=local?'local':'pc';localMode=local;clearTimeout(retryTimer);
    $('app-modes')?.classList.add('hidden');$('change-mode')?.classList.remove('hidden');
    $('pc-mode').classList.toggle('hidden',local);$('local-mode')?.classList.toggle('hidden',!local);
    $('mode-local')?.classList.toggle('active',local);$('mode-pc')?.classList.toggle('active',!local);
    if(local){stopPhoneVision();window.stopPhoneTracking();try{localModule ||= import('./phone-local.js');await localModule;await window.sakuraLocalVisible(true);}catch(error){$('local-status').textContent=error.message;}}
    else{window.sakuraLocalVisible?.(false);manualDisconnect=false;autoReconnect();}
}
$('mode-local')?.addEventListener('click',()=>selectMode(true));$('mode-pc')?.addEventListener('click',()=>selectMode(false));
$('change-mode')?.addEventListener('click',()=>{
    selectedMode=null;localMode=false;clearTimeout(retryTimer);stopPhoneVision();window.stopPhoneTracking();window.sakuraLocalVisible?.(false);
    $('pc-mode').classList.add('hidden');$('local-mode').classList.add('hidden');$('app-modes').classList.remove('hidden');$('change-mode').classList.add('hidden');
});
const request=(path,body)=>{const data=JSON.parse(Sakura.request(body===undefined?'GET':'POST',path,JSON.stringify(body||{})));if(data.error)throw Error(data.error);return data;};
const command=body=>request('/command',body);
let visionStream=null,visionTimer=null;
function stopPhoneVision(notify=true){
    clearInterval(visionTimer);visionTimer=null;visionStream?.getTracks().forEach(t=>t.stop());visionStream=null;
    const video=$('phone-camera-preview');if(video)video.srcObject=null;
    if($('camera-share'))$('camera-share').textContent='Share camera with Companion';
    if(notify&&connected)try{command({type:'camera-stop'});}catch(_){}
}
window.stopPhoneVision=stopPhoneVision;
$('camera-share')?.addEventListener('click',async()=>{
    if(visionStream){stopPhoneVision();return;}
    window.stopPhoneTracking();
    try{
        const stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:$('camera-facing').value,width:{ideal:480},height:{ideal:360}}});
        if(!connected){stream.getTracks().forEach(t=>t.stop());return;}
        visionStream=stream;const video=$('phone-camera-preview');video.srcObject=stream;await video.play();
        command({type:'camera-start'});$('camera-share').textContent='Stop sharing camera';
        status('Camera shared for Companion viewing · tracking off');
        const canvas=document.createElement('canvas');
        visionTimer=setInterval(()=>{
            if(!connected||!visionStream||video.readyState<2)return;
            canvas.width=480;canvas.height=Math.max(1,Math.round(480*video.videoHeight/video.videoWidth));
            const context=canvas.getContext('2d');context.drawImage(video,0,0,canvas.width,canvas.height);
            try{request('/camera',{image:canvas.toDataURL('image/jpeg',.55).split(',')[1]});}catch(error){status(error.message);}
            context.clearRect(0,0,canvas.width,canvas.height);
        },1000);
    }catch(error){stopPhoneVision();status(error.message);}
});
window.addEventListener('pagehide',()=>stopPhoneVision());
const viewer={live2d:true,setUserTracking(value){remoteTracking=value;},updateUserTracking(data){
    if(!remoteTracking||frameBusy||!data.face?.matrix)return;
    frameBusy=true;try{request('/frame',{face:{...data.face,matrix:Array.from(data.face.matrix)},headPoseFiltered:data.headPoseFiltered===true});}catch(error){status(error.message);}finally{frameBusy=false;}
},calibrateUserTracking(){command({type:'calibrate'});}};
const tracker=new AvatarTracking(viewer,status);tracker.handTrackingEnabled=false;tracker.frameRate=24;
tracker.cameraFacingMode=localStorage.getItem('sakura-phone-camera')==='environment'?'environment':'user';
$('camera-facing').value=tracker.cameraFacingMode;
$('camera').style.transform=tracker.cameraFacingMode==='user'?'scaleX(-1)':'none';
// Attach the actual MediaPipe camera video after it is opened.
const start=tracker.start.bind(tracker);tracker.start=async()=>{await start();$('camera').srcObject=tracker.stream;};
window.stopPhoneTracking=()=>{tracker.stop();remoteTracking=false;$('camera').srcObject=null;$('tracking').textContent='Start camera tracking';if(connected)try{command({type:'tracking-stop'});}catch(_){};};
function connectedPc(data){if(data.error)throw Error(data.error);connected=true;manualDisconnect=false;$('pair').classList.add('hidden');$('controls').classList.remove('hidden');$('disconnect').classList.remove('hidden');status('Connected to '+data.name+' · '+data.edition);if(data.edition==='vtuber')document.querySelector('[data-tab="expression"]').click();}
$('connect').onclick=()=>{try{connectedPc(JSON.parse(Sakura.connect($('address').value.trim(),$('code').value.trim())));}catch(error){status(error.message);}};
function remembered(){
    const list=$('remembered-devices');list.replaceChildren();
    let computers=[];try{if(Sakura.remembered)computers=JSON.parse(Sakura.remembered());}catch(_){}
    for(const pc of computers){const button=document.createElement('button');button.textContent=pc.name+' · '+pc.address;button.onclick=async()=>{manualDisconnect=false;try{await reconnect(pc.address);}catch(error){status(error.message+' Saved pairing kept. Make sure the PC and phone are on the same network.');}};list.append(button);}
    if(!computers.length)list.textContent='No saved PCs yet. Choose New device to pair.';
    return computers.length;
}
$('existing-device').onclick=()=>{remembered();$('remembered-devices').classList.remove('hidden');$('new-pair').classList.add('hidden');};
$('new-device').onclick=()=>{$('remembered-devices').classList.add('hidden');$('new-pair').classList.remove('hidden');};
if(remembered())$('existing-device').click();else $('new-device').click();
$('disconnect').onclick=()=>{manualDisconnect=true;clearTimeout(retryTimer);stopPhoneVision();window.stopPhoneTracking();connected=false;$('pair').classList.remove('hidden');$('controls').classList.add('hidden');$('disconnect').classList.add('hidden');remembered();status('Disconnected · pairing remembered');};
document.querySelectorAll('[data-tab]').forEach(button=>button.onclick=()=>{for(const id of ['companion','expression','vtuber'])$(id).classList.toggle('hidden',id!==button.dataset.tab);$('phone-camera-section')?.classList.toggle('hidden',button.dataset.tab!=='companion');document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b===button));});
$('tracking').onclick=async()=>{if(remoteTracking){window.stopPhoneTracking();return;}if($('tracking').disabled)return;stopPhoneVision();$('tracking').disabled=true;try{await tracker.start();command({type:'tracking-start'});$('tracking').textContent='Stop camera tracking';}catch(error){window.stopPhoneTracking();status(error.message);}finally{$('tracking').disabled=false;}};
$('camera-facing').onchange=()=>{const restart=remoteTracking;window.stopPhoneTracking();tracker.cameraFacingMode=$('camera-facing').value;localStorage.setItem('sakura-phone-camera',tracker.cameraFacingMode);$('camera').style.transform=tracker.cameraFacingMode==='user'?'scaleX(-1)':'none';if(restart)$('tracking').click();};
$('calibrate').onclick=()=>{try{command({type:'calibrate'});status('PC neutral pose calibrated');}catch(error){status(error.message);}};
$('clear').onclick=()=>{try{command({type:'clear-expressions'});active.clear();renderExpressions();}catch(error){status(error.message);}};
function renderExpressions(){const list=$('expressions');list.replaceChildren();for(const name of expressions){const button=document.createElement('button');button.textContent=name;button.classList.toggle('active',active.has(name));button.onclick=()=>{try{const enabled=!active.has(name);command({type:'expression',name,enabled});if(enabled)active.add(name);else active.delete(name);button.classList.toggle('active',enabled);}catch(error){status(error.message);}};list.append(button);}}
$('gemini').onclick=()=>{try{request('/gemini',{key:$('key').value});$('key').value='';status('Gemini selected on the PC');}catch(error){status(error.message);}};
$('send').onclick=()=>{const text=$('message').value.trim();if(!text)return;$('send').disabled=true;status('Sakura is thinking…');setTimeout(()=>{try{const data=request('/chat',{text});$('conversation').textContent+='You: '+text+'\nSakura: '+data.reply+'\n\n';$('message').value='';status('Connected');}catch(error){status(error.message);}finally{$('send').disabled=false;}},30);};
setInterval(()=>{if(!connected||frameBusy||selectedMode!=='pc')return;try{const data=request('/state');if(data.avatar){$('avatar').src='data:image/jpeg;base64,'+data.avatar;$('avatar').style.display='block';}else $('avatar').style.display='none';const next=data.expressions||[];if(JSON.stringify(next)!==JSON.stringify(expressions)){expressions=next;active.clear();renderExpressions();}}catch(error){connected=false;stopPhoneVision(false);window.stopPhoneTracking();status(error.message);autoReconnect();}},2000);
if(!standaloneAvailable){$('pc-mode').classList.remove('hidden');setTimeout(autoReconnect,100);}
