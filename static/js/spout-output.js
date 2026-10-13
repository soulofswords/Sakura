export function installSpoutControls(getViewer) {
    const toggle=document.getElementById('spout-enabled'),name=document.getElementById('spout-name');
    const fps=document.getElementById('spout-fps'),size=document.getElementById('spout-resolution'),status=document.getElementById('spout-status');
    let token='',generation=0,timer=null;
    async function disable() {
        generation++;token='';clearTimeout(timer);toggle.checked=false;getViewer()?.releaseSpoutFrame();
        await fetch('/api/spout/configure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:false})});
    }
    async function send(g) {
        if(!token || g!==generation)return;
        const started=performance.now();
        try {
            const frame=getViewer()?.captureSpoutFrame(Number(size.value));
            if(frame){
                const response=await fetch(`/api/spout/frame?width=${frame.width}&height=${frame.height}`,{method:'POST',headers:{'Content-Type':'application/octet-stream','x-spout-session':token},body:frame.pixels});
                if(!response.ok){const data=await response.json();throw Error(data.error||'Spout frame failed.');}
                status.textContent=`Sending ${frame.width} × ${frame.height}. In OBS select Spout2 Capture → ${name.value || 'Sakura'}.`;
            } else status.textContent='Spout enabled. Load a character to begin output.';
            if(g===generation)timer=setTimeout(()=>send(g),Math.max(0,1000/Number(fps.value)-(performance.now()-started)));
        }catch(error){if(g!==generation)return;await disable();status.textContent=error.message;}
    }
    toggle.onchange=async()=>{
        toggle.disabled=true;
        try {
            if(!toggle.checked){await disable();status.textContent='Spout output is off.';return;}
            const response=await fetch('/api/spout/configure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:true,name:name.value || 'Sakura'})});
            const data=await response.json();if(!response.ok)throw Error(data.error);
            token=data.token;localStorage.setItem('sakura_spout_name',name.value||'Sakura');send(++generation);
        }catch(error){toggle.checked=false;status.textContent=error.message;}
        finally{toggle.disabled=false;name.disabled=toggle.checked;}
    };
    name.value=localStorage.getItem('sakura_spout_name')||'Sakura';
    fetch('/api/spout/status').then(r=>r.json()).then(data=>{
        if(!data.supported){toggle.disabled=true;status.textContent='Spout2 requires Windows. Use OBS window capture on macOS.';}
    }).catch(()=>{status.textContent='Spout service unavailable.';toggle.disabled=true;});
    window.addEventListener('pagehide',()=>{
        if(token)navigator.sendBeacon('/api/spout/configure',new Blob([JSON.stringify({enabled:false})],{type:'application/json'}));
        token='';clearTimeout(timer);getViewer()?.releaseSpoutFrame();
    });
}
