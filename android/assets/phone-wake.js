import {nativeJob} from './native-jobs.js';
const $=id=>document.getElementById(id);
export function wakeSettings(){
    let busy=false,errorText='',dirty=false;
    function refresh(){if(!Sakura.wakeState)return;try{const data=JSON.parse(Sakura.wakeState());$('local-wake').checked=!!data.enabled;window.sakuraWakeStatus?.(!!data.enabled);$('local-wake').disabled=busy||!data.installed;$('local-wake-phrase').disabled=busy||!!data.enabled;if(!dirty&&document.activeElement!==$('local-wake-phrase'))$('local-wake-phrase').value=data.phrase||'hey sakura';$('local-wake-download').hidden=!!data.installed;$('local-wake-download').disabled=busy||!!data.download_active;$('local-wake-download').textContent=data.download_active?'Downloading…':data.download_bytes?'Resume download · '+(data.download_bytes/1000000).toFixed(1)+' MB saved':'Download offline wake pack · 40 MB';$('local-wake-status').textContent=data.download_active?(data.download_status||'Connecting to wake pack server…'):errorText|| (data.enabled?(data.status||'Starting wake detector…'):(data.installed?(data.status||'Wake phrase off · turn it on while Sakura is open'):'Download the optional offline wake pack first.'));}catch(_){}}
    async function action(button,method,...args){if(busy)return;busy=true;errorText='';button.disabled=true;button.setAttribute('aria-busy','true');try{await nativeJob(method,...args);dirty=false;refresh();}catch(error){errorText=error.message;$('local-wake-status').textContent=error.message;}finally{busy=false;button.disabled=false;button.removeAttribute('aria-busy');const enabled=JSON.parse(Sakura.wakeState?.()||'{}');$('local-wake').checked=!!enabled.enabled;$('local-wake').disabled=!enabled.installed;$('local-wake-phrase').disabled=!!enabled.enabled;}}
    $('local-wake-phrase').oninput=()=>{dirty=true;errorText='';};
    $('local-wake-download').onclick=()=>action($('local-wake-download'),'installWakePack');
    $('local-wake').onchange=()=>action($('local-wake'),'setWake',$('local-wake').checked,$('local-wake-phrase').value.trim());
    window.sakuraRefreshWake=refresh;
    setInterval(()=>{if(!document.hidden)refresh();},1000);refresh();
}
