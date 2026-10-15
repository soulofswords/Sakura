export function createVoiceRuntime(getVoice){
    let ready=false,pending=null;
    const modal=document.getElementById('kokoro-loading-modal'),message=document.getElementById('kokoro-loading-message');
    const error=document.getElementById('kokoro-loading-error'),close=document.getElementById('kokoro-loading-close');
    close?.addEventListener('click',()=>modal?.classList.add('hidden'));
    return async function ensureKokoroReady(){
        if(String(getVoice()).startsWith('system_')||ready)return;
        if(pending)return pending;
        pending=(async()=>{
            const response=await fetch('/api/tts/kokoro',{cache:'no-store'}),state=await response.json();
            if(!response.ok)throw Error(state.error||'Local speech runtime is unavailable. Restart Sakura after updating.');
            if(state.phase==='ready'){ready=true;return;}
            modal?.classList.remove('hidden');close?.classList.add('hidden');if(error)error.textContent='';
            if(message)message.textContent=state.message||'Loading local Kokoro voices…';
            let checking=false;
            const timer=setInterval(async()=>{
                if(checking)return;checking=true;
                try{const r=await fetch('/api/tts/kokoro',{cache:'no-store'}),s=await r.json();if(message)message.textContent=s.message+(s.phase==='downloading'?` ${s.progress}%`:'');}
                catch(_){}finally{checking=false;}
            },500);
            try{
                const r=await fetch('/api/tts/kokoro',{method:'POST'}),s=await r.json();
                if(!r.ok||s.phase!=='ready')throw Error(s.error||s.message||'Kokoro could not load.');
                ready=true;modal?.classList.add('hidden');
            }catch(exception){if(error)error.textContent=exception.message;close?.classList.remove('hidden');throw exception;}
            finally{clearInterval(timer);}
        })();
        try{return await pending;}finally{pending=null;}
    };
}
