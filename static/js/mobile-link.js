import HeadPoseFilter from './head-pose-filter.js?v=1';
export function installMobileLink(getViewer,getTracker,onReply,openSettings){
    const toggle=document.getElementById('phone-link-enabled'),status=document.getElementById('phone-link-status');
    let enabled=false,busy=false,remote=false,filter=new HeadPoseFilter(),lastState=0,lastRemoteFrame=0;
    const devices=document.getElementById('phone-link-devices');
    const show=data=>{enabled=!!data.enabled;toggle.checked=enabled;
        document.getElementById('phone-link-address').value=enabled?(data.addresses||[])[0]||'':'';
        document.getElementById('phone-link-code').value=enabled?data.code||'':'';
        for(const kind of ['address','code'])document.getElementById('phone-link-copy-'+kind).disabled=!document.getElementById('phone-link-'+kind).value;
        if(devices){
            devices.replaceChildren();
            for(const device of data.devices||[]){
                const row=document.createElement('div'),label=document.createElement('span'),forget=document.createElement('button');
                row.className='camera-phone-row';label.textContent=device.name+' · '+(device.connected?'Connected':'Remembered');
                forget.textContent='Forget';forget.onclick=async()=>{try{show(await(await fetch('/api/mobile/link',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({forget:device.id})})).json());}catch(error){status.textContent=error.message;}};
                row.append(label,forget);devices.append(row);
            }
            if(!(data.devices||[]).length)devices.textContent='No remembered phones. Choose New device to pair your Android phone.';
        }
        status.textContent=enabled
        ?`PC address: ${(data.addresses||[]).join(' or ')||'Check your PC Wi-Fi IPv4 address'} · Pairing code: ${data.code} (valid for 5 minutes)`:'Phone connection off';};
    for(const kind of ['address','code'])document.getElementById('phone-link-copy-'+kind).onclick=async()=>{
        const input=document.getElementById('phone-link-'+kind);if(!input.value)return;
        try{
            let copied=false;
            if(window.pywebview?.api?.copy_text){try{copied=!!(await window.pywebview.api.copy_text(input.value))?.copied;}catch(_){} }
            if(!copied&&navigator.clipboard?.writeText){try{await navigator.clipboard.writeText(input.value);copied=true;}catch(_){} }
            if(!copied){input.focus();input.select();if(!document.execCommand('copy'))throw Error('Select the text and press Ctrl+C.');}
            status.textContent=kind==='address'?'Connection link copied.':'Pairing code copied.';
        }catch(error){input.focus();input.select();status.textContent='Copy unavailable. Press Ctrl+C on the selected text.';}
    };
    fetch('/api/mobile/link').then(r=>r.json()).then(show).catch(()=>{});
    document.getElementById('phone-link-existing')?.addEventListener('click',async()=>{
        if(devices)devices.hidden=false;
        try{show(await(await fetch('/api/mobile/link')).json());}catch(error){status.textContent=error.message;}
    });
    document.getElementById('phone-link-new')?.addEventListener('click',async()=>{
        try{
            if(!enabled)show(await(await fetch('/api/mobile/link',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:true})})).json());
            show(await(await fetch('/api/mobile/link',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({new:true})})).json());
            status.textContent+=' · Enter this code on your new phone.';
        }catch(error){status.textContent=error.message;}
    });
    toggle.onchange=async()=>{try{show(await(await fetch('/api/mobile/link',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:toggle.checked})})).json());}
        catch(error){status.textContent=error.message;toggle.checked=enabled;}};
    const connectPhone=()=>{
        document.getElementById('tracking-modal')?.classList.add('hidden');
        openSettings();document.querySelector('.tab-btn[data-tab="general"]')?.click();
        if(!enabled){toggle.checked=true;toggle.dispatchEvent(new Event('change'));}
        toggle.scrollIntoView({block:'center'});
    };
    for(const id of ['connect-phone-btn','tracking-connect-phone-btn','settings-connect-phone-btn'])document.getElementById(id)?.addEventListener('click',connectPhone);
    let state={};
    async function poll(){
        if(!enabled||busy||!getViewer())return;
        busy=true;const viewer=getViewer();
        try{
            if(performance.now()-lastState>1500){
                state={edition:window.SAKURA_EDITION||'companion',expressions:viewer.allMorphNames||[],
                    model:viewer.lastModelUrl||'',tracking:remote,avatar:viewer.model?viewer.captureAvatar():null};lastState=performance.now();
            }
            const response=await fetch('/api/mobile/poll',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(state)});
            if(!response.ok)return;
            const data=await response.json();if(!data.enabled){enabled=false;toggle.checked=false;remote=false;viewer.setUserTracking(false);window.dispatchEvent(new CustomEvent('sakura-phone-camera',{detail:{type:'camera-stop'}}));return;}
            for(const command of data.commands||[]){
                if(command.type==='tracking-start'){
                    getTracker()?.stop();remote=true;filter=new HeadPoseFilter();
                    window.dispatchEvent(new CustomEvent('sakura-phone-tracking',{detail:true}));
                    viewer.setVtuberTrackingMode(true);viewer.setUserTracking(true);
                }else if(command.type==='tracking-stop'){remote=false;viewer.setUserTracking(false);}
                else if(command.type==='camera-start'||command.type==='camera-stop'){
                    if(command.type==='camera-start'){remote=false;viewer.setUserTracking(false);}
                    window.dispatchEvent(new CustomEvent('sakura-phone-camera',{detail:command}));
                }
                else if(command.type==='calibrate')viewer.calibrateUserTracking();
                else if(command.type==='clear-expressions')viewer.clearManualExpression();
                else if(command.type==='expression'&&(viewer.allMorphNames||[]).includes(command.name)){
                    if(viewer.areAiExpressionsAutomatic?.())continue;
                    viewer.manualExpressions ||= new Map();
                    if(command.enabled===false){viewer.manualExpressions.delete(command.name);if(viewer.manualExpression?.name===command.name)viewer.manualExpression=null;viewer.live2d?.removeExpression(command.name);viewer.setMorph(command.name,0);}
                    else{viewer.manualExpressions.set(command.name,1);viewer.live2d?.setExpression(command.name,1);}
                }else if(command.type==='phone-reply')onReply(command.text);
            }
            if(data.camera)window.dispatchEvent(new CustomEvent('sakura-phone-camera-frame',{detail:data.camera}));
            if(remote&&data.frame){
                data.frame.timestamp=performance.now();
                if(!data.frame.headPoseFiltered)data.frame.face=filter.update(data.frame.face,data.frame.timestamp);
                viewer.updateUserTracking({...data.frame,handTrackingEnabled:false});
                lastRemoteFrame=performance.now();
            }else if(remote&&performance.now()-lastRemoteFrame>600){
                viewer.updateUserTracking({face:{landmarks:[],blendshapes:[],matrix:null},hands:[],pose:null,handTrackingEnabled:false});
            }
        }catch(error){status.textContent='Phone connection: '+error.message;}
        finally{busy=false;}
    }
    setInterval(()=>poll(),33);
}
