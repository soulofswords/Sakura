export function desktopWakeControls({continuousMic,settings,blocked,receive,status}){
    const download=document.getElementById('desktop-wake-download'),label=document.getElementById('desktop-wake-status');
    const api=()=>window.pywebview?.api;
    let enabled=false,installing=false,syncing=false,last='',busy=false,audio=false;
    const pause=async value=>{busy=!!value;return api()?.pause_wake_listener?.(busy||audio);};
    const audioActive=async value=>{audio=!!value;return api()?.pause_wake_listener?.(busy||audio);};
    async function refresh(){if(!api()?.wake_state)return;try{const state=await api().wake_state();enabled=!!state.enabled;label.textContent=state.status;download.hidden=!!state.installed;download.disabled=installing||!state.available;}catch(error){label.textContent=error.message;}}
    async function sync(force=false){
        if(!api()?.set_wake_listener||syncing)return;
        const config=settings(),wanted=!!config.wake_word_enabled&&!blocked()&&!continuousMic.userRequested,key=String(wanted)+'|'+config.wake_word;
        if(!force&&key===last)return;syncing=true;
        try{if(wanted)continuousMic.stop();const state=await api().set_wake_listener(wanted,config.wake_word||'hey sakura');if(state.error)throw Error(state.error);enabled=!!state.enabled;last=key;label.textContent=state.status;await refresh();}
        catch(error){last=key;enabled=false;label.textContent=error.message;status(error.message);}
        finally{syncing=false;}
    }
    download.onclick=async()=>{if(installing||!api()?.install_wake_pack)return;installing=true;download.disabled=true;download.textContent='Downloading wake pack…';try{const result=await api().install_wake_pack();if(result.error)throw Error(result.error);await sync(true);}catch(error){label.textContent=error.message;}finally{installing=false;download.textContent='Download offline PC wake pack · 55 MB';await refresh();}};
    window.receiveDesktopWakeCommand=async text=>{if(blocked()||!enabled||!settings().wake_word_enabled){await pause(false);return false;}try{await receive(String(text).slice(0,10000));return true;}finally{await pause(false);}};
    window.stopDesktopWakeFromTray=async()=>{enabled=false;last='false|';document.getElementById('wake-word-toggle').checked=false;document.getElementById('wake-word-toggle').dispatchEvent(new Event('change'));await refresh();};
    window.addEventListener('sakura-native-visibility',event=>{window.sakuraNativeHidden=!!event.detail?.hidden;});
    setInterval(()=>{refresh();sync();},2000);window.addEventListener('pywebviewready',()=>{refresh();sync();});
    return {sync,refresh,enabled:()=>enabled,pause,audioActive};
}
