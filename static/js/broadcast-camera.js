export function findBroadcastCamera(devices){
    return devices.find(d=>d.kind==='videoinput'&&/(?:nvidia.*broadcast|broadcast.*nvidia)/i.test(d.label||''))||null;
}
export function installBroadcastCamera({refresh,select,status,open}){
    const button=document.getElementById('tracking-broadcast-camera');
    button.onclick=async()=>{
        button.disabled=true;
        try{
            const devices=await navigator.mediaDevices.enumerateDevices();
            const camera=findBroadcastCamera(devices);
            if(!camera){status.textContent='NVIDIA Broadcast camera was not found. Open Broadcast, select your webcam there, then refresh cameras. If camera labels are hidden, start regular tracking once to grant camera access.';return;}
            await refresh();select.value=camera.deviceId;select.dispatchEvent(new Event('change'));
            status.textContent='NVIDIA Broadcast camera selected. Turn Eye Contact off in Broadcast to preserve your real gaze and blink. Use Start tracking, then calibrate. This input supplies video, not extra expression coefficients.';
        }catch(error){status.textContent=error.message;}
        finally{button.disabled=false;}
    };
    document.getElementById('tracking-broadcast-open').onclick=async()=>{
        try{const result=await open?.();status.textContent=result?.ok?'Broadcast opened. Configure your webcam there, then choose Use Broadcast camera.':result?.error||'Open NVIDIA Broadcast on your PC, then choose Use Broadcast camera.';}
        catch(error){status.textContent=error.message;}
    };
}
