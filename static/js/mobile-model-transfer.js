// A paired phone may request a picker, but only a local selection can expose files.
export async function openMobileModelTransfer(requestId){
    const previous=document.getElementById('mobile-model-transfer-dialog');if(previous){previous.close();previous.remove();}
    const dialog=document.createElement('dialog');dialog.id='mobile-model-transfer-dialog';
    Object.assign(dialog.style,{background:'#151023',color:'#f5f2ff',border:'1px solid #655080',borderRadius:'18px',padding:'24px',maxWidth:'520px',width:'90vw'});
    const heading=document.createElement('h2');heading.textContent='Send models to your phone';
    const description=document.createElement('p');description.textContent='Tick every model to send. The phone collects one model per tap of Add model, so keep tapping until the batch is through.';
    const types=document.createElement('div'),message=document.createElement('p'),entry=document.createElement('div'),send=document.createElement('button'),cancel=document.createElement('button');
    entry.hidden=true;entry.setAttribute('role','group');entry.setAttribute('aria-label','Models to send');
    entry.style.cssText='display:grid;gap:5px;max-height:190px;overflow:auto;margin:10px 0;padding:2px';
    send.hidden=true;send.textContent='Send selected models';cancel.textContent='Cancel';
    message.setAttribute('role','status');message.setAttribute('aria-live','polite');
    const progress=document.createElement('progress');progress.hidden=true;progress.style.width='100%';progress.setAttribute('aria-label','Models sent from this batch');
    let selection,expecting=requestId,all_sent=false;
    const report=async(status,error='',request=requestId)=>{const response=await fetch('/api/mobile/transfer-status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:request,status,error})});if(!response.ok)throw Error((await response.json()).error||'Transfer request expired.');};
    async function close(){
        // Abandoning the batch has to clear the PC queue too, or the next phone tap would
        // quietly deliver a model the user stopped asking for.
        if(!all_sent){try{await report('cancelled','Closed from the PC.',expecting);}catch(_){}}
        dialog.close();dialog.remove();
    }
    cancel.onclick=close;dialog.addEventListener('cancel',event=>{event.preventDefault();close();});
    for(const kind of ['pmx','live2d','vrm']){
        const button=document.createElement('button');button.textContent=kind==='vrm'?'VRM files':kind==='pmx'?'PMX folder':'Live2D folder';
        button.onclick=async()=>{
            for(const b of types.children)b.disabled=true;message.textContent='Choose '+(kind==='vrm'?'the VRM files':'the entire model folder')+'…';
            try{
                if(!window.pywebview?.api?.choose_mobile_model_package)throw Error('Restart the updated desktop app to use the native folder picker.');
                const data=await window.pywebview.api.choose_mobile_model_package(kind);if(data.error)throw Error(data.error);
                if(data.cancelled){message.textContent='Nothing selected. Choose another folder or Cancel.';return;}
                selection=data.selection;
                entry.replaceChildren(...data.entries.map((name,index)=>{
                    const box=document.createElement('input');box.type='checkbox';box.value=String(index);box.checked=data.entries.length===1;
                    const label=document.createElement('label');label.style.cssText='display:flex;gap:8px;align-items:center';
                    label.append(box,document.createTextNode(name));return label;
                }));
                entry.hidden=false;send.hidden=false;
                message.textContent=data.folder+' · '+data.entries.length+' model(s). Tick the ones to send.';
            }catch(error){message.textContent=error.message;}finally{for(const b of types.children)b.disabled=false;}
        };types.append(button);
    }
    const picked=()=>[...entry.querySelectorAll('input')].filter(box=>box.checked).map(box=>Number(box.value));
    send.onclick=async()=>{
        if(!selection||send.disabled)return;
        const wanted=picked();
        if(!wanted.length){message.textContent='Tick at least one model to send.';return;}
        send.disabled=true;send.setAttribute('aria-busy','true');send.textContent='Preparing model…';progress.hidden=false;progress.max=wanted.length;progress.value=0;cancel.disabled=true;entry.disabled=true;entry.style.pointerEvents='none';for(const b of types.children)b.disabled=true;message.textContent='Packing '+(wanted.length>1?wanted.length+' models':'the model')+' for your phone…';
        try{
            if(!window.pywebview?.api?.send_mobile_model_package)throw Error('Restart the updated PC app to enable model transfer.');
            await report('preparing');const data=await window.pywebview.api.send_mobile_model_package(selection,wanted,requestId);if(data.error)throw Error(data.error);
            let sent=0,total=wanted.length,deadline=Date.now()+600000;
            send.textContent='Waiting for phone…';
            message.textContent=data.model.name+' prepared. Waiting for the phone to finish downloading…';
            while(dialog.isConnected&&Date.now()<deadline){
                const response=await fetch('/api/mobile/transfer-status'),status=await response.json();
                if(!response.ok)throw Error(status.error||'Transfer status could not be checked.');
                const request=status.request;
                if(!request)throw Error('The transfer request expired. Check the phone, then choose Add model to retry.');
                // The phone asks for the next queued model with a brand new request id, so
                // follow it instead of treating the change as an expired transfer.
                expecting=request.id;
                if(request.status==='ready'){
                    progress.value=sent;
                    message.textContent='Model '+(sent+1)+' of '+total+' · '+((request.model&&request.model.name)||'your model')+' is on the phone. Waiting for it to save…';
                }else if(request.status==='received'){
                    sent++;progress.value=sent;deadline=Date.now()+600000;
                    if(sent>=total){all_sent=true;cancel.textContent='Close';send.textContent='All sent ✓';message.textContent='All '+total+' models are saved on the phone.';return;}
                    send.textContent='Sent '+sent+' of '+total+' …';
                    message.textContent='Model '+sent+' of '+total+' saved on the phone. Tap Add model there for the next one.';
                }else if(['failed','cancelled'].includes(request.status))throw Error(request.error||'Transfer cancelled. Choose Add model on the phone to retry.');
                await new Promise(resolve=>setTimeout(resolve,1000));
            }
            if(dialog.isConnected)throw Error('The phone has not confirmed receipt. Check its connection and retry Add model.');
        }
        catch(error){message.textContent='Transfer failed: '+error.message;send.textContent='Not sent';progress.hidden=true;try{await report('failed',error.message,expecting);}catch(_){}cancel.textContent='Close';}
        finally{send.removeAttribute('aria-busy');cancel.disabled=false;}
    };
    dialog.append(heading,description,types,message,entry,progress,send,cancel);document.body.append(dialog);dialog.showModal();
    try{await window.pywebview?.api?.show_phone_transfer?.();}catch(_){}
}
