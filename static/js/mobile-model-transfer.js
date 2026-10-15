// A paired phone may request a picker, but only a local selection can expose files.
export async function openMobileModelTransfer(requestId){
    const previous=document.getElementById('mobile-model-transfer-dialog');if(previous){previous.close();previous.remove();}
    const dialog=document.createElement('dialog');dialog.id='mobile-model-transfer-dialog';
    Object.assign(dialog.style,{background:'#151023',color:'#f5f2ff',border:'1px solid #655080',borderRadius:'18px',padding:'24px',maxWidth:'520px',width:'90vw'});
    const heading=document.createElement('h2');heading.textContent='Send a model to your phone';
    const description=document.createElement('p');description.textContent='Choose a complete folder for PMX or Live2D. All files inside that folder will be sent. For VRM, choose a single .vrm file.';
    const types=document.createElement('div'),message=document.createElement('p'),entry=document.createElement('select'),send=document.createElement('button'),cancel=document.createElement('button');
    entry.hidden=true;send.hidden=true;send.textContent='Send selected model';cancel.textContent='Cancel';
    message.setAttribute('role','status');message.setAttribute('aria-live','polite');
    const progress=document.createElement('progress');progress.hidden=true;progress.style.width='100%';progress.setAttribute('aria-label','Model transfer progress');
    let selection,finished=false;
    const report=async(status,error='')=>{const response=await fetch('/api/mobile/transfer-status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:requestId,status,error})});if(!response.ok)throw Error((await response.json()).error||'Transfer request expired.');};
    async function close(){if(!finished){try{await report('cancelled');}catch(_){} }dialog.close();dialog.remove();}
    cancel.onclick=close;dialog.addEventListener('cancel',event=>{event.preventDefault();close();});
    for(const kind of ['pmx','live2d','vrm']){
        const button=document.createElement('button');button.textContent=kind==='vrm'?'VRM file':kind==='pmx'?'PMX folder':'Live2D folder';
        button.onclick=async()=>{
            for(const b of types.children)b.disabled=true;message.textContent='Choose '+(kind==='vrm'?'one VRM file':'the entire model folder')+'…';
            try{
                if(!window.pywebview?.api?.choose_mobile_model_package)throw Error('Restart the updated desktop app to use the native folder picker.');
                const data=await window.pywebview.api.choose_mobile_model_package(kind);if(data.error)throw Error(data.error);
                if(data.cancelled){message.textContent='Nothing selected. Choose another folder or Cancel.';return;}
                selection=data.selection;entry.replaceChildren(...data.entries.map((name,index)=>{const option=document.createElement('option');option.value=String(index);option.textContent=name;return option;}));
                entry.hidden=false;send.hidden=false;message.textContent=data.folder+' · '+data.entries.length+' model(s). '+(kind==='vrm'?'Only the VRM file will be sent.':'The entire selected folder will be sent.');
            }catch(error){message.textContent=error.message;}finally{for(const b of types.children)b.disabled=false;}
        };types.append(button);
    }
    send.onclick=async()=>{
        if(!selection||send.disabled)return;send.disabled=true;send.setAttribute('aria-busy','true');send.textContent='Preparing model…';progress.hidden=false;cancel.disabled=true;entry.disabled=true;for(const b of types.children)b.disabled=true;message.textContent='Send clicked · Packing the model for your phone…';
        try{
            if(!window.pywebview?.api?.send_mobile_model_package)throw Error('Restart the updated PC app to enable model transfer.');
            await report('preparing');const data=await window.pywebview.api.send_mobile_model_package(selection,Number(entry.value),requestId);if(data.error)throw Error(data.error);
            finished=true;send.textContent='Waiting for phone…';message.textContent=data.model.name+' prepared. Waiting for the phone to finish downloading…';cancel.textContent='Close';cancel.disabled=false;
            const deadline=Date.now()+600000;
            while(dialog.isConnected&&Date.now()<deadline){
                const response=await fetch('/api/mobile/transfer-status'),status=await response.json();
                if(!response.ok)throw Error(status.error||'Transfer status could not be checked.');
                const request=status.request;
                if(!request||request.id!==requestId)throw Error('The transfer request expired. Check the phone, then choose Add model to retry.');
                if(request.status==='received'){
                    send.textContent='Sent ✓';progress.value=1;progress.max=1;message.textContent=data.model.name+' successfully saved on the phone. Loading the model there…';return;
                }
                if(['failed','cancelled'].includes(request.status))throw Error(request.error||'Transfer cancelled. Choose Add model on the phone to retry.');
                await new Promise(resolve=>setTimeout(resolve,1000));
            }
            if(dialog.isConnected)throw Error('The phone has not confirmed receipt. Check its connection and retry Add model.');
        }
        catch(error){message.textContent='Transfer failed: '+error.message;send.textContent='Not sent';progress.hidden=true;try{await report('failed',error.message);}catch(_){}cancel.textContent='Close';}
        finally{send.removeAttribute('aria-busy');cancel.disabled=false;}
    };
    dialog.append(heading,description,types,message,progress,entry,send,cancel);document.body.append(dialog);dialog.showModal();
    try{await window.pywebview?.api?.show_phone_transfer?.();}catch(_){}
}
