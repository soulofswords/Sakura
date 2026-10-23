export function installVirtualCamera(getViewer) {
    const buttons=[document.getElementById('virtual-camera-toggle'),document.getElementById('virtual-camera-settings-toggle')];
    const status=document.getElementById('virtual-camera-status');
    let token='',generation=0,timer=null;
    const update=busy=>buttons.forEach(button=>{
        button.disabled=busy;button.textContent=token?'Virtual Camera: On':'Virtual Camera: Off';
        button.setAttribute('aria-pressed',String(Boolean(token)));
    });
    async function stop() {
        generation++;clearTimeout(timer);token='';update(true);
        const response=await fetch('/api/virtual-camera/configure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:false})});
        if(!response.ok)throw Error((await response.json()).error||'Could not stop virtual camera.');
    }
    async function send(g) {
        if(!token||g!==generation)return;
        try {
            const frame=getViewer()?.captureSpoutFrame(720);
            if(frame) {
                const response=await fetch(`/api/virtual-camera/frame?width=${frame.width}&height=${frame.height}`,{
                    method:'POST',headers:{'Content-Type':'application/octet-stream','x-camera-session':token},body:frame.pixels});
                const data=await response.json();if(!response.ok)throw Error(data.error||'Virtual camera stopped.');
                if(g!==generation)return;
                status.textContent=`Virtual camera on. Select ${data.device||'OBS Virtual Camera'} in your video app. 1280 × 720 output.`;
            } else status.textContent='Virtual camera waiting for the character to finish loading…';
            if(g===generation)timer=setTimeout(()=>send(g),67);
        }catch(error){
            if(g!==generation)return;
            try{await stop();}catch(_){}update(false);status.textContent=error.message;
        }
    }
    buttons.forEach(button=>button.addEventListener('click',async()=>{
        update(true);
        try {
            if(token){await stop();status.textContent='Virtual camera off.';return;}
            if(!getViewer()?.captureSpoutFrame(720))throw Error('Load a character before enabling Virtual Camera.');
            status.textContent='Starting virtual camera…';
            const response=await fetch('/api/virtual-camera/configure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:true})});
            const data=await response.json();if(!response.ok)throw Error(data.error||'Virtual camera could not start.');
            token=data.token;send(++generation);
        }catch(error){status.textContent=error.message;}
        finally{update(false);}
    }));
    update(false);
    window.addEventListener('pagehide',()=>{
        if(token)navigator.sendBeacon('/api/virtual-camera/configure',new Blob([JSON.stringify({enabled:false})],{type:'application/json'}));
        token='';generation++;clearTimeout(timer);
    });
}
