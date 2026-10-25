import AvatarTracking from '/static/js/avatar-tracking.js';
import {installButtonFeedback} from '/static/js/button-feedback.js';
installButtonFeedback();
import {nativeJob} from './native-jobs.js';
const $=id=>document.getElementById(id),status=message=>$('status').textContent=message;
let connected=false,remoteTracking=false,companionTracking=false,frameBusy=false,expressions=[],active=new Set();
let localMode=false,reconnecting=null,manualDisconnect=false,retryTimer=null,retryDelay=2000;
const standaloneAvailable=Boolean(Sakura.localAvailable?.());
let selectedMode=standaloneAvailable?null:'pc';
async function reconnect(computerId,address){
    if(reconnecting)return reconnecting;
    reconnecting=(async()=>{try{const data=await nativeJob('reconnectAsync',computerId||'',address||'');connectedPc(data);retryDelay=2000;localStorage.setItem('sakura-last-pc',computerId||address||'');return data;}finally{reconnecting=null;}})();return reconnecting;
}
function savedComputers(){try{return JSON.parse(Sakura.remembered());}catch(_){return [];}}
async function autoReconnect(forTransfer=false){
    clearTimeout(retryTimer);if((selectedMode!=='pc'&&!forTransfer)||manualDisconnect||connected||reconnecting)return;
    const computers=savedComputers(),last=localStorage.getItem('sakura-last-pc');const pc=computers.find(p=>p.id===last||p.address===last)||computers.at(-1);if(!pc)return;
    try{await reconnect(pc.id||'',pc.address||'');}catch(error){status('PC not available yet. Saved pairing kept; retrying automatically. '+error.message);retryTimer=setTimeout(autoReconnect,retryDelay);retryDelay=Math.min(30000,retryDelay*2);}
}
window.sakuraEnsurePc=async()=>{if(connected)return;manualDisconnect=false;await autoReconnect(true);if(!connected)throw Error('Open the paired PC app for this one-time model transfer. Existing phone models and Local chat do not require the PC.');};
window.sakuraResume=()=>{window.sakuraRefreshLocation?.();window.sakuraRefreshWake?.();window.sakuraRefreshWakeHistory?.();document.getElementById('local-avatar')?.contentWindow?.phoneAvatar?.pause(false);autoReconnect();};
let localModule;
async function selectMode(local){
    selectedMode=local?'local':'pc';localMode=local;clearTimeout(retryTimer);
    $('app-modes')?.classList.add('hidden');$('change-mode')?.classList.remove('hidden');
    $('pc-mode').classList.toggle('hidden',local);$('local-mode')?.classList.toggle('hidden',!local);
    $('mode-local')?.classList.toggle('active',local);$('mode-pc')?.classList.toggle('active',!local);
    if(local){stopPhoneVision();window.stopPhoneTracking();try{localModule ||= import('./phone-local.js');await localModule;await window.sakuraLocalVisible(true);}catch(error){$('local-status').textContent=error.message;}}
    else{window.sakuraLocalVisible?.(false);manualDisconnect=false;renderSaved();void searchPcs();autoReconnect();}
}
$('mode-local')?.addEventListener('click',()=>selectMode(true));$('mode-pc')?.addEventListener('click',()=>selectMode(false));
$('change-mode')?.addEventListener('click',()=>{
    selectedMode=null;localMode=false;clearTimeout(retryTimer);stopPhoneVision();window.stopPhoneTracking();window.sakuraLocalVisible?.(false);
    $('pc-mode').classList.add('hidden');$('local-mode').classList.add('hidden');$('app-modes').classList.remove('hidden');$('change-mode').classList.add('hidden');
});
const request=(path,body)=>{const data=JSON.parse(Sakura.request(body===undefined?'GET':'POST',path,JSON.stringify(body||{})));if(data.error)throw Error(data.error);return data;};
const command=body=>request('/command',body);
let visionStream=null,visionTimer=null,cameraRevision=0;
function stopPhoneVision(notify=true){
    cameraRevision++;
    clearInterval(visionTimer);visionTimer=null;visionStream?.getTracks().forEach(t=>t.stop());visionStream=null;
    const video=$('phone-camera-preview');if(video)video.srcObject=null;
    if($('camera-share'))$('camera-share').textContent=$('phone-companion-camera-mode')?.value==='tracking'?'Start face tracking':'Start object recognition';
    if(notify&&connected)try{command({type:'camera-stop'});}catch(_){}
}
window.stopPhoneVision=stopPhoneVision;
$('camera-share')?.addEventListener('click',async()=>{
    if($('camera-share').disabled)return;
    if(!connected){status('Connect to your PC before starting the Companion camera.');return;}
    if($('phone-companion-camera-mode').value==='tracking'){
        if(companionTracking){window.stopPhoneTracking();return;}
        stopPhoneVision();window.stopPhoneTracking();const revision=cameraRevision;$('camera-share').disabled=true;
        try{
            tracker.cameraFacingMode=$('phone-companion-camera-facing').value;
            localStorage.setItem('sakura-phone-camera',tracker.cameraFacingMode);
            $('camera').style.transform=tracker.cameraFacingMode==='user'?'scaleX(-1)':'none';
            await tracker.start();
            if(!connected||revision!==cameraRevision)return;
            const preview=$('phone-camera-preview');preview.srcObject=tracker.stream;preview.style.transform=tracker.cameraFacingMode==='user'?'scaleX(-1)':'none';await preview.play();
            if(revision!==cameraRevision)return;
            companionTracking=true;command({type:'companion-tracking-start'});
            $('camera-share').textContent='Stop face tracking';status('Phone face tracking on · Companion AI remains available');
        }catch(error){if(revision===cameraRevision){window.stopPhoneTracking();status(error.message);}}
        finally{$('camera-share').disabled=false;}
        return;
    }
    if(visionStream){stopPhoneVision();return;}
    window.stopPhoneTracking();const revision=cameraRevision;$('camera-share').disabled=true;
    try{
        const facing=$('phone-companion-camera-facing').value;tracker.cameraFacingMode=facing;$('camera-facing').value=facing;localStorage.setItem('sakura-phone-camera',facing);
        const stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:{exact:facing},width:{ideal:480},height:{ideal:360}}});
        if(!connected||revision!==cameraRevision){stream.getTracks().forEach(t=>t.stop());return;}
        visionStream=stream;const video=$('phone-camera-preview');video.srcObject=stream;video.style.transform=facing==='user'?'scaleX(-1)':'none';await video.play();
        if(revision!==cameraRevision)return;
        command({type:'camera-start'});$('camera-share').textContent='Stop object recognition';
        status('Object recognition on · camera images go to the paired PC');
        const canvas=document.createElement('canvas');
        visionTimer=setInterval(()=>{
            if(!connected||!visionStream||video.readyState<2)return;
            canvas.width=480;canvas.height=Math.max(1,Math.round(480*video.videoHeight/video.videoWidth));
            const context=canvas.getContext('2d');context.drawImage(video,0,0,canvas.width,canvas.height);
            try{request('/camera',{image:canvas.toDataURL('image/jpeg',.55).split(',')[1]});}catch(error){status(error.message);}
            context.clearRect(0,0,canvas.width,canvas.height);
        },1000);
    }catch(error){if(revision===cameraRevision){stopPhoneVision();status(error.message);}}
    finally{$('camera-share').disabled=false;}
});
window.addEventListener('pagehide',()=>{stopPhoneVision();window.stopPhoneTracking();});
let trackingSequence=0,lastRtxFrame=0,lastUploadedFps=0;
let pcNvidiaFrames=false;const rtxCanvas=document.createElement('canvas');
const viewer={live2d:false,setUserTracking(value){remoteTracking=value;},async updateUserTracking(data){
    if(!remoteTracking||(frameBusy&&!Sakura.submitTrackingFrame))return;
    frameBusy=true;try{
    let cameraFrame;
    if(pcNvidiaFrames&&tracker.video?.videoWidth&&performance.now()-lastRtxFrame>=1000/tracker.frameRate){
        lastRtxFrame=performance.now();
        const w=Math.min(480,tracker.video.videoWidth),h=Math.round(w*tracker.video.videoHeight/tracker.video.videoWidth);
        rtxCanvas.width=w;rtxCanvas.height=h;rtxCanvas.getContext('2d',{alpha:false}).drawImage(tracker.video,0,0,w,h);
        cameraFrame={image:rtxCanvas.toDataURL('image/jpeg',.6).split(',')[1],width:w,height:h};
    }
    const packet=JSON.stringify({cameraFrame,face:{...data.face,matrix:data.face?.matrix?Array.from(data.face.matrix):null},headPoseFiltered:data.headPoseFiltered===true,hands:data.hands||[],pose:data.pose||null,handTrackingEnabled:data.handTrackingEnabled!==false,
        trackingMetrics:{sequence:++trackingSequence,cameraFps:tracker.cameraFrameRate||0,processedFps:tracker.measuredFps||0,uploadedFps:lastUploadedFps,processingMs:data.processingMs||0}});
    if(Sakura.submitTrackingFrame)Sakura.submitTrackingFrame(packet);else await nativeJob('trackingFrameAsync',packet);
}catch(error){status(error.message);}finally{frameBusy=false;}
},calibrateUserTracking(){command({type:'calibrate'});}};
const performanceLabel=document.createElement('p');performanceLabel.id='tracking-performance';performanceLabel.setAttribute('role','status');$('vtuber').append(performanceLabel);
window.sakuraTrackingTransport=(fps,dropped,ms,error)=>{
    lastUploadedFps=fps;
    performanceLabel.textContent=`Target ${tracker.frameRate} FPS · camera ${Math.round(tracker.cameraFrameRate||0)} · face inference ${tracker.measuredFps||0} · uploaded ${fps} FPS · network ${Math.round(ms)} ms · replaced ${dropped} pending frames`+(error?' · '+error:'');
};
const tracker=new AvatarTracking(viewer,status);tracker.handTrackingEnabled=true;tracker.frameRate=60;tracker.captureWidth=640;tracker.captureHeight=480;tracker.inferenceWidth=480;tracker.poseStride=1;tracker.handStride=3;tracker.preferGPU=true;tracker.lowLatency=true;
const rateLabel=document.createElement('label');rateLabel.htmlFor='phone-tracking-rate';rateLabel.textContent='Tracking performance';
const rate=document.createElement('select');rate.id='phone-tracking-rate';rate.add(new Option('60 FPS target · low latency','60'));rate.add(new Option('30 FPS target · lower battery use','30'));
try{rate.value=localStorage.getItem('sakura-phone-tracking-rate')==='30'?'30':'60';}catch(_){}
const rateHint=document.createElement('small');rateHint.textContent='Actual FPS depends on camera and inference speed. In 60 FPS mode, face and shoulders are processed on every source frame; hands update up to 20 FPS when enabled. Uses more battery. NVIDIA image forwarding targets the selected rate; actual speed depends on your phone, Wi-Fi and PC.';
$('vtuber').querySelector('h2').after(rateLabel,rate,rateHint);
const configureRate=()=>{const fast=rate.value==='60';tracker.frameRate=fast?60:30;tracker.poseStride=1;tracker.handStride=fast?3:2;tracker.lowLatency=fast;tracker.inferenceWidth=fast?480:640;};configureRate();
rate.onchange=()=>{if(remoteTracking)window.stopPhoneTracking();configureRate();localStorage.setItem('sakura-phone-tracking-rate',rate.value);status('Tracking rate changed. Tap Start camera tracking to resume.');};
tracker.cameraFacingMode=localStorage.getItem('sakura-phone-camera')==='environment'?'environment':'user';
$('camera-facing').value=tracker.cameraFacingMode;
$('phone-companion-camera-facing').value=tracker.cameraFacingMode;
$('camera').style.transform=tracker.cameraFacingMode==='user'?'scaleX(-1)':'none';
// Attach the actual MediaPipe camera video after it is opened.
const start=tracker.start.bind(tracker);tracker.start=async()=>{await start();$('camera').srcObject=tracker.stream;};
window.stopPhoneTracking=()=>{cameraRevision++;Sakura.stopTrackingFrames?.();const wasCompanion=companionTracking;tracker.stop();remoteTracking=false;$('camera').srcObject=null;if(wasCompanion)$('phone-camera-preview').srcObject=null;$('tracking').textContent='Start camera tracking';if(connected)try{command({type:wasCompanion?'companion-tracking-stop':'tracking-stop'});}catch(_){};companionTracking=false;if($('camera-share'))$('camera-share').textContent=$('phone-companion-camera-mode')?.value==='tracking'?'Start face tracking':'Start object recognition';};
function connectedPc(data){if(data.error)throw Error(data.error);connected=true;manualDisconnect=false;$('pair').classList.add('hidden');$('controls').classList.remove('hidden');$('disconnect').classList.remove('hidden');status('Connected to '+data.name+' · '+data.edition);if(data.edition==='vtuber')document.querySelector('[data-tab="expression"]').click();}
let pairingPc=null,searching=false;
function pcRow(label,detail,onClick){
    const button=document.createElement('button'),name=document.createElement('b'),sub=document.createElement('small');
    name.textContent=label;sub.textContent=detail;button.append(name,document.createElement('br'),sub);button.onclick=onClick;return button;
}
function showPairForm(pc){
    pairingPc=pc;$('pair-code').classList.remove('hidden');
    $('pair-target').textContent=`Enter the 6-digit code shown on “${pc.name||'this PC'}”.`;
    $('code').value='';$('code').focus();
}
async function pairWith(address,code,button,fingerprint){
    if(!/^\d{6}$/.test(code)){status('Enter the 6-digit code shown on your PC.');return;}
    button.disabled=true;
    try{connectedPc(await nativeJob('connectAsync',address,code,fingerprint||''));$('advanced-pair').open=false;}
    catch(error){status(error.message+' Keep the PC app open and check that Connect to Phone is on.');}
    finally{button.disabled=false;}
}
$('connect').onclick=()=>{if(!pairingPc){status('Choose your PC from the list first.');return;}return pairWith(pairingPc.https,$('code').value.trim(),$('connect'),pairingPc.fingerprint);};
$('choose-another-pc').onclick=()=>{pairingPc=null;$('pair-code').classList.add('hidden');};
$('manual-connect').onclick=()=>{
    const host=$('host').value.trim(),port=$('port').value.trim(),usable=/^\d{1,5}$/.test(port)&&+port>0&&+port<=65535;
    if(!/^\d{1,3}(\.\d{1,3}){3}$/.test(host)){status('Enter the PC’s IPv4 address, for example 192.168.1.10.');return;}
    return pairWith('https://'+host+':'+(usable?port:'8771'),$('manual-code').value.trim(),$('manual-connect'),'');
};
function renderSaved(){
    const list=$('saved-pcs');list.replaceChildren();
    const computers=savedComputers().filter(pc=>pc.credential);
    for(const pc of computers)list.append(pcRow(pc.name||'Sakura',(pc.edition||'companion')+' · remembered · no code needed',async()=>{
        manualDisconnect=false;list.querySelectorAll('button').forEach(b=>b.disabled=true);
        try{await reconnect(pc.id||'',pc.address||'');}
        catch(error){status(error.message+' Saved pairing kept. Make sure the PC and phone are on the same network.');}
        finally{list.querySelectorAll('button').forEach(b=>b.disabled=false);}
    }));
    return computers.length;
}
async function searchPcs(){
    if(searching)return;searching=true;
    const button=$('rescan-pcs');button.disabled=true;
    $('discover-status').textContent='Searching this Wi-Fi for PCs running Sakura…';
    try{
        const found=(await nativeJob('discoverAsync')).computers||[];
        const paired=new Set(savedComputers().map(pc=>pc.id));
        const list=$('discovered-pcs');list.replaceChildren();
        for(const pc of found){
            const known=paired.has(pc.id);
            list.append(pcRow(pc.name||'Sakura',(known?'Remembered · ':'New · ')+(pc.edition||'companion'),async()=>{
                if(!known){showPairForm(pc);return;}
                manualDisconnect=false;list.querySelectorAll('button').forEach(b=>b.disabled=true);
                try{await reconnect(pc.id,'');}
                catch(error){status(error.message+' Saved pairing kept. Make sure the PC and phone are on the same network.');}
                finally{list.querySelectorAll('button').forEach(b=>b.disabled=false);}
            }));
        }
        $('discover-status').textContent=found.length
            ?`Found ${found.length} ${found.length===1?'PC running':'PCs running'} Sakura · tap yours, then enter the 6-digit code.`
            :'No PC answered. Keep the PC app open and turn on Connect to Phone in its Settings → General. Guest Wi-Fi and VPNs block discovery — use Advanced below.';
    }catch(error){$('discover-status').textContent='Search failed: '+error.message;}
    finally{searching=false;button.disabled=false;}
}
$('rescan-pcs').onclick=()=>searchPcs();
renderSaved();
$('disconnect').onclick=()=>{manualDisconnect=true;clearTimeout(retryTimer);stopPhoneVision();window.stopPhoneTracking();connected=false;pairingPc=null;$('pair-code').classList.add('hidden');$('pair').classList.remove('hidden');$('controls').classList.add('hidden');$('disconnect').classList.add('hidden');renderSaved();void searchPcs();status('Disconnected · pairing remembered');};
document.querySelectorAll('[data-tab]').forEach(button=>button.onclick=()=>{for(const id of ['companion','expression','vtuber','pc-tools'])$(id).classList.toggle('hidden',id!==button.dataset.tab);$('phone-camera-section')?.classList.toggle('hidden',button.dataset.tab!=='companion');document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b===button));});
$('tracking').onclick=async()=>{if(remoteTracking){window.stopPhoneTracking();return;}if($('tracking').disabled)return;stopPhoneVision();$('tracking').disabled=true;try{await tracker.start();command({type:'tracking-start'});$('tracking').textContent='Stop camera tracking';}catch(error){window.stopPhoneTracking();status(error.message);}finally{$('tracking').disabled=false;}};
$('phone-companion-camera-mode').onchange=()=>{stopPhoneVision();window.stopPhoneTracking();$('camera-share').textContent=$('phone-companion-camera-mode').value==='tracking'?'Start face tracking':'Start object recognition';};
function setPhoneCameraFacing(value){$('camera-facing').value=value;$('phone-companion-camera-facing').value=value;tracker.cameraFacingMode=value;localStorage.setItem('sakura-phone-camera',value);$('camera').style.transform=value==='user'?'scaleX(-1)':'none';}
$('camera-facing').onchange=()=>{const restart=remoteTracking,wasCompanion=companionTracking;window.stopPhoneTracking();setPhoneCameraFacing($('camera-facing').value);if(wasCompanion)$('camera-share').click();else if(restart)$('tracking').click();};
$('phone-companion-camera-facing').onchange=()=>{
    const value=$('phone-companion-camera-facing').value;
    const restart=companionTracking||Boolean(visionStream);
    // Release the previous camera before opening the other Android lens.
    if(visionStream)stopPhoneVision();
    window.stopPhoneTracking();
    setPhoneCameraFacing(value);
    if(restart)$('camera-share').click();
};
$('calibrate').onclick=()=>{try{command({type:'calibrate'});status('PC neutral pose calibrated');}catch(error){status(error.message);}};
$('clear').onclick=()=>{try{command({type:'clear-expressions'});active.clear();renderExpressions();}catch(error){status(error.message);}};
function renderExpressions(){const list=$('expressions');list.replaceChildren();for(const name of expressions){const button=document.createElement('button');button.textContent=name;button.classList.toggle('active',active.has(name));button.onclick=()=>{try{const enabled=!active.has(name);command({type:'expression',name,enabled});if(enabled)active.add(name);else active.delete(name);button.classList.toggle('active',enabled);}catch(error){status(error.message);}};list.append(button);}}
$('gemini').onclick=()=>{try{request('/gemini',{key:$('key').value});$('key').value='';status('Gemini selected on the PC');}catch(error){status(error.message);}};
$('send').onclick=()=>{const text=$('message').value.trim();if(!text)return;$('send').disabled=true;status('Sakura is thinking…');setTimeout(()=>{try{const data=request('/chat',{text});$('conversation').textContent+='You: '+text+'\nSakura: '+data.reply+'\n\n';$('message').value='';status('Connected');}catch(error){status(error.message);}finally{$('send').disabled=false;}},30);};
let phoneStateBusy=false,lastTrackingControl=0;
setInterval(async()=>{if(!connected||phoneStateBusy||selectedMode!=='pc')return;phoneStateBusy=true;try{const data=await nativeJob('trackingStateAsync');pcNvidiaFrames=data.tracking_face_source==='nvidia_ar';const c=data.tracking_control;if(c&&c.id!==lastTrackingControl&&c.expires*1000>Date.now()){lastTrackingControl=c.id;if(c.action==='stop')window.stopPhoneTracking();else if(c.action==='hands')tracker.setHandTracking(c.enabled===true);else if(c.action==='calibrate')$('calibrate').click();else if(c.action==='start'&&!remoteTracking&&!companionTracking)$('tracking').click();}if(data.avatar){$('avatar').src='data:image/jpeg;base64,'+data.avatar;$('avatar').style.display='block';}else $('avatar').style.display='none';const next=data.expressions||[];if(JSON.stringify(next)!==JSON.stringify(expressions)){expressions=next;active.clear();renderExpressions();}const live=(data.active_expressions||[]).filter(name=>expressions.includes(name));if(live.slice().sort().join('\n')!==[...active].filter(name=>expressions.includes(name)).sort().join('\n')){active.clear();for(const name of live)active.add(name);renderExpressions();}}catch(error){connected=false;stopPhoneVision(false);window.stopPhoneTracking();status(error.message);autoReconnect();}finally{phoneStateBusy=false;}},500);
if(!standaloneAvailable){$('pc-mode').classList.remove('hidden');setTimeout(autoReconnect,100);}

// Explicit paired-device tools. No background clipboard polling.
for(const [id,makePayload]of Object.entries({
 'pc-status-refresh':()=>({action:'system.status'}),
 'pc-volume-set':()=>({action:'audio.volume',operation:'set',value:Number($('pc-volume').value)}),
 'pc-clipboard-get':()=>({action:'clipboard.read'}),
 'pc-clipboard-send':()=>({action:'clipboard.write',text:$('pc-clipboard').value})
}))$(''+id)?.addEventListener('click',async()=>{
 const button=$(id);if(!connected){$('pc-tools-status').textContent='Connect to your PC first.';return;}
 button.disabled=true;button.setAttribute('aria-busy','true');$('pc-tools-status').textContent='Requesting PC tool…';
 try{await new Promise(r=>setTimeout(r,30));const payload=makePayload(),data=request('/tools',payload);
  if(payload.action==='clipboard.read'){$('pc-clipboard').value=data.text||'';$('pc-tools-status').textContent='PC clipboard received.';}
  else $('pc-tools-status').textContent=data.reply||'Clipboard sent to PC.';
 }catch(error){$('pc-tools-status').textContent=error.message;}finally{button.disabled=false;button.removeAttribute('aria-busy');}
});
