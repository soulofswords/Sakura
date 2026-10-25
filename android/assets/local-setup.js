import {nativeJob} from './native-jobs.js';
import {installProviderTools} from './provider-tools.js';
const $=id=>document.getElementById(id);
function popup(title){
    const dialog=document.createElement('dialog');dialog.className='local-setup-dialog';
    const h=document.createElement('h2');h.textContent=title;const content=document.createElement('div'),message=document.createElement('p'),cancel=document.createElement('button');
    message.setAttribute('role','status');cancel.textContent='Cancel';dialog.append(h,content,message,cancel);document.body.append(dialog);dialog.showModal();
    let cancelled=false,resolveCancel;const dismissed=new Promise(resolve=>resolveCancel=resolve);
    const close=(dismiss=true)=>{cancelled=true;dialog.close();dialog.remove();if(dismiss)resolveCancel(null);};
    cancel.onclick=close;dialog.addEventListener('cancel',event=>{event.preventDefault();close();});
    return {dialog,content,message,cancel,close,dismissed,get cancelled(){return cancelled;}};
}
function field(parent,label,tag='input',options=[]){const text=document.createElement('label');text.textContent=label;const input=document.createElement(tag);for(const [value,label]of options){const option=document.createElement('option');option.value=value;option.textContent=label;input.append(option);}parent.append(text,input);return input;}
export async function apiSetup(){
    const modal=popup('1 · Choose your AI provider'),config=JSON.parse(Sakura.localConfig());
    const provider=field(modal.content,'API provider','select',[['gemini','Google Gemini'],['openai','OpenAI']]);provider.value=config.provider;
    const key=field(modal.content,'API key');key.type='password';key.autocomplete='off';key.placeholder=config.key_set?'Saved key · leave blank to keep':'Enter your API key';
    const model=field(modal.content,'AI model ID');model.value=config.model;
    const voice=field(modal.content,'Voice','select',[['female','Female'],['male','Male']]);voice.value=config.voice;
    provider.onchange=()=>{model.value=provider.value==='gemini'?'gemini-flash-latest':'gpt-4.1-mini';};
    installProviderTools(modal.content,{provider,key,model,voice,address:()=>config.address||'sir',status:text=>modal.message.textContent=text});
    modal.message.textContent='Your key stays encrypted on this phone. AI replies use internet; the PC is only needed for the initial model transfer.';
    const next=document.createElement('button');next.textContent='Save and continue';modal.content.append(next);
    const done=new Promise(resolve=>next.onclick=()=>{try{
        const current=JSON.parse(Sakura.localConfig());
        if(!key.value.trim()&&(!current.key_set||provider.value!==current.provider))throw Error('Enter the API key for the selected provider.');
        const result=JSON.parse(Sakura.configureLocal(provider.value,key.value.trim(),model.value.trim(),voice.value,config.address||'sir'));if(result.error)throw Error(result.error);
        key.value='';modal.close(false);resolve(result);
    }catch(error){modal.message.textContent=error.message;}});
    return Promise.race([done,modal.dismissed]);
}
export async function chooseSavedModel(){
    const models=JSON.parse(Sakura.localModels());if(!models.length)return {add:true};
    const modal=popup('Choose your phone model'),select=field(modal.content,'Saved models','select',models.map(m=>[m.id,m.name+' · '+m.format.toUpperCase()]));
    const saved=localStorage.getItem('sakura-local-model');if(models.some(m=>m.id===saved))select.value=saved;
    const use=document.createElement('button'),add=document.createElement('button');use.textContent='Use model';add.textContent='Add model';modal.content.append(use,add);
    modal.message.textContent='Saved models load from this phone. No PC connection is needed.';
    const done=new Promise(resolve=>{use.onclick=()=>{const model=models.find(m=>m.id===select.value);modal.close(false);resolve({model});};add.onclick=()=>{modal.close(false);resolve({add:true});};});
    return Promise.race([done,modal.dismissed]);
}
export async function transferSetup(){
    const modal=popup('2 · Connect to PC for model transfer');
    const intro=document.createElement('p');intro.textContent='Use the same Wi-Fi for this one-time transfer. Enable Connect to Phone on your PC. After transfer, Local works away from home.';modal.content.append(intro);
    const saved=JSON.parse(Sakura.remembered()||'[]'),last=localStorage.getItem('sakura-last-pc'),recent=saved.find(p=>p.address===last)||saved.at(-1);
    const pc=field(modal.content,'Remembered PC','select',saved.map(p=>[p.address,p.name+' · '+p.address]));if(recent)pc.value=recent.address;
    const address=field(modal.content,'PC address (for a new PC)');address.placeholder='https://192.168.1.10:8771';address.inputMode='url';
    const code=field(modal.content,'Pairing code (new PC only)');code.inputMode='numeric';code.maxLength=6;
    const connect=document.createElement('button');connect.textContent='Connect / retry';modal.content.append(connect);
    let pending=false,activeRequest='';
    modal.dismissed.then(()=>{if(activeRequest)void nativeJob('cancelModelTransfer',activeRequest).catch(()=>{});});
    const done=new Promise(resolve=>{
        async function start(){
            if(pending||modal.cancelled)return;pending=true;connect.disabled=true;connect.setAttribute('aria-busy','true');connect.textContent='Connecting…';
            try{
                modal.message.textContent='Connecting…';
                const data=address.value.trim()?await nativeJob('connectAsync',address.value.trim(),code.value.trim(),''):pc.value?await nativeJob('reconnectAsync',pc.value):null;
                if(!data)throw Error('Enter the PC address and pairing code, or choose a remembered PC.');
                if(modal.cancelled)return;code.value='';localStorage.setItem('sakura-last-pc',address.value.trim()||pc.value);
                modal.message.textContent='Connection Passed · Waiting for you to select the model on your PC…';
                connect.textContent='Waiting for PC…';
                const request=await nativeJob('requestModelTransfer');const requestId=request.request_id;activeRequest=requestId;
                if(modal.cancelled){void nativeJob('cancelModelTransfer',requestId).catch(()=>{});return;}
                const deadline=Date.now()+600000;
                while(!modal.cancelled&&Date.now()<deadline){
                    const state=await nativeJob('phoneState');const transfer=state.transfer_request;
                    if(!transfer||transfer.id!==requestId)throw Error('The model request expired. Retry the connection.');
                    if(transfer.status==='failed'||transfer.status==='cancelled')throw Error(transfer.error||'Model selection was cancelled on the PC. Retry when ready.');
                    if(transfer.status==='ready'){
                        modal.message.textContent='Connection Passed · Downloading model folder to this phone…';
                        connect.textContent='Downloading model…';
                        const model=await nativeJob('receiveModel',requestId);if(modal.cancelled)return;
                        modal.close(false);resolve(model);return;
                    }
                    modal.message.textContent=transfer.status==='preparing'?'Connection Passed · Preparing your model and all folder files…':'Connection Passed · Choose PMX, Live2D or VRM in the PC popup, then click Send selected model.';
                    await new Promise(resolve=>setTimeout(resolve,1000));
                }
                if(!modal.cancelled)throw Error('Model transfer timed out. Retry when your PC is ready.');
            }catch(error){if(activeRequest){void nativeJob('cancelModelTransfer',activeRequest).catch(()=>{});activeRequest='';}if(!modal.cancelled)modal.message.textContent='Connection / transfer Failed · '+error.message;}
            finally{pending=false;connect.disabled=false;connect.removeAttribute('aria-busy');connect.textContent='Connect / retry';}
        }
        connect.onclick=start;
        if(recent)setTimeout(start,100);else modal.message.textContent='Connect the PC using its address and pairing code. The result will show Passed or Failed here.';
    });
    return Promise.race([done,modal.dismissed]);
}
