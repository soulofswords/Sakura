import {nativeJob} from './native-jobs.js';
const $=id=>document.getElementById(id);
export function modelStage({send,status,canListen}){
    let ready=false,full=false,mic=false,wake=false,blocked=true;
    const button=$('local-mic'),slash=button.querySelector('[data-mic-slash]');
    function micState(on,message){mic=!!on;const active=mic||wake;button.setAttribute('aria-pressed',String(active));button.setAttribute('aria-label',active?'Turn microphone off':'Turn microphone on');button.classList.toggle('listening',active);button.disabled=blocked&&!wake;slash.style.display=active?'none':'';$('local-mic-label').textContent=mic?'Mic on':wake?'Wake on':'Mic off';if(message)status(message);}
    window.sakuraWakeStatus=enabled=>{wake=!!enabled;micState(mic);};
    function stopMic(){const active=mic;micState(false);if(active)Sakura.setMicrophone?.(false);}
    function fullscreen(value){full=!!value&&ready;document.body.classList.toggle('local-model-fullscreen',full);$('local-stage-panel').classList.remove('stage-panel-open');$('local-panel-toggle').setAttribute('aria-expanded','false');$('local-panel-toggle').setAttribute('aria-label','Open menu');Sakura.setModelFullscreen?.(full);if(!full)stopMic();}
    $('local-stage-back').onclick=()=>fullscreen(false);
    $('local-stage-expand').onclick=()=>fullscreen(true);
    $('local-panel-toggle').onclick=()=>{const open=$('local-stage-panel').classList.toggle('stage-panel-open');$('local-panel-toggle').setAttribute('aria-expanded',String(open));$('local-panel-toggle').setAttribute('aria-label',open?'Close menu':'Open menu');};
    button.onclick=async()=>{if(wake&&!mic){wake=false;micState(false);try{await nativeJob('setWake',false,'');window.sakuraRefreshWake?.();status('Wake listening off');}catch(error){status(error.message);window.sakuraRefreshWake?.();}return;}if(mic){stopMic();status('Microphone off');return;}if(!canListen())return;if(!Sakura.setMicrophone){status('Update the APK to use the microphone button.');return;}micState(true,'Starting microphone…');Sakura.setMicrophone(true);};
    window.sakuraMicrophone=(on,message,text)=>{if(on&&!mic)return;const accept=mic;micState(on,message);if(text&&accept&&canListen()){$('local-message').value=String(text).slice(0,10000);send();}};
    window.sakuraExitModelFullscreen=()=>{fullscreen(false);$('local-stage-expand').focus();};
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&full){event.preventDefault();window.sakuraExitModelFullscreen();}});
    return {
        loaded(value){ready=!!value;$('local-stage-controls').hidden=!ready;$('local-stage-expand').hidden=!ready;fullscreen(ready);},
        gate(disabled){blocked=!!disabled;if(disabled)stopMic();else micState(mic);},stopMic,
        exit(){ready=false;fullscreen(false);$('local-stage-controls').hidden=true;$('local-stage-expand').hidden=true;}
    };
}
