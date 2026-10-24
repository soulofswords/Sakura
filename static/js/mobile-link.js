import HeadPoseFilter from './head-pose-filter.js?v=1';
export function installMobileLink(getViewer,getTracker,onReply,openSettings){
    const toggle=document.getElementById('phone-link-enabled'),status=document.getElementById('phone-link-status');
    let enabled=false,busy=false,remote=false,remoteKind='',filter=new HeadPoseFilter(),lastState=0,lastRemoteFrame=0;
    const devices=document.getElementById('phone-link-devices');
    const address=document.getElementById('phone-link-address');
    if(address&&!document.getElementById('phone-link-advanced')){
        const advanced=document.createElement('details');advanced.id='phone-link-advanced';
        const summary=document.createElement('summary');summary.textContent='Advanced connection troubleshooting';advanced.append(summary);
        const label=document.querySelector('label[for="phone-link-address"]'),copy=document.getElementById('phone-link-copy-address');
        address.before(advanced);if(label)advanced.append(label);advanced.append(address);if(copy)advanced.append(copy);
    }
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
        ?`On Sakura Mobile, choose Connect to PC → “${data.name||'Sakura'}”, then enter the pairing code below. Both devices must be on the same Wi-Fi. The code is valid for 5 minutes.`:'Phone connection off';};
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
    let remoteSamples=0,remoteStarted=0;
    // A phone that is already streaming does not resend tracking-start after
    // the PC window restarts. Accept its frames after an explicit PC Start.
    window.addEventListener('sakura-phone-tracking-requested',event=>{
        remote=event.detail?.enabled===true;
        remoteKind=remote?'vtuber':'';
        if(getTracker())getTracker().remoteActive=remote;
        if(remote){filter=new HeadPoseFilter();remoteSamples=0;remoteStarted=performance.now();}
        getViewer()?.setVtuberTrackingMode(remote);
        getViewer()?.setUserTracking(remote);
    });
    const trackingStatus=message=>{
        for(const id of ['tracking-status','settings-camera-status']){
            const label=document.getElementById(id);if(label)label.textContent=message;
        }
    };
    let state={};
    document.getElementById('tracking-hands-enabled')?.addEventListener('click',e=>{
        if(!enabled)return;
        fetch('/api/mobile/tracking-control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'hands',enabled:e.currentTarget.getAttribute('aria-pressed')==='true'})})
            .then(async r=>{if(!r.ok)throw Error((await r.json()).error||'Could not update phone hand tracking');})
            .catch(error=>{status.textContent='Phone tracking: '+error.message;});
    });
    document.getElementById('send-model-mobile')?.addEventListener('click',async()=>{
        const button=document.getElementById('send-model-mobile');button.disabled=true;
        try{
            const response=await fetch('/api/mobile/transfer-status'),data=await response.json();if(!response.ok)throw Error(data.error);
            if(!data.enabled)throw Error('Enable Connect to Phone, then on the phone choose Local → Add model.');
            if(!data.request||data.request.status!=='waiting')throw Error('On your phone choose Local → Add model. The PMX/Live2D folder or VRM file picker will open here automatically.');
            const {openMobileModelTransfer}=await import('./mobile-model-transfer.js?v=phone-touch73');await openMobileModelTransfer(data.request.id);
        }catch(error){status.textContent=error.message;openSettings();document.querySelector('.tab-btn[data-tab="general"]')?.click();}
        finally{button.disabled=false;}
    });
    async function poll(){
        if(!enabled||busy||!getViewer())return;
        busy=true;const viewer=getViewer();
        if(getTracker())getTracker().remoteActive=remote;
        try{
            if(performance.now()-lastState>1500){
                const names=viewer.allMorphNames||[];
                state={edition:window.SAKURA_EDITION||'companion',expressions:names,
                    active_expressions:[...(viewer.manualExpressions?.keys()||[])].filter(name=>names.includes(name)),
                    model:viewer.lastModelUrl||'',tracking:remote,tracking_face_source:getTracker()?.faceSource||'webcam',avatar:viewer.model&&!remote?viewer.captureAvatar():null};lastState=performance.now();
            }
            const response=await fetch('/api/mobile/poll',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(state)});
            if(!response.ok)return;
            const data=await response.json();if(!data.enabled){enabled=false;toggle.checked=false;remote=false;viewer.setUserTracking(false);if(remoteKind==='companion'){viewer.setVtuberTrackingMode(false);viewer.setCompanionTracking(false);window.dispatchEvent(new CustomEvent('sakura-phone-companion-tracking',{detail:{enabled:false}}));}remoteKind='';window.dispatchEvent(new CustomEvent('sakura-phone-camera',{detail:{type:'camera-stop'}}));return;}
            for(const command of data.commands||[]){
                if(command.type==='request-model'){
                    void import('./mobile-model-transfer.js?v=phone-touch73').then(module=>module.openMobileModelTransfer(command.request_id)).catch(error=>{status.textContent=error.message;});
                }else if(command.type==='tracking-start'){
                    getTracker()?.stop();remote=true;remoteKind='vtuber';filter=new HeadPoseFilter();remoteSamples=0;remoteStarted=performance.now();trackingStatus('Sakura Mobile · waiting for tracking frames');
                    window.dispatchEvent(new CustomEvent('sakura-phone-tracking',{detail:true}));
                    viewer.setCompanionTracking(false);viewer.setVtuberTrackingMode(true);viewer.setUserTracking(true);
                }else if(command.type==='companion-tracking-start'){
                    getTracker()?.stop();remote=true;remoteKind='companion';filter=new HeadPoseFilter();remoteSamples=0;remoteStarted=performance.now();trackingStatus('Sakura Mobile · waiting for tracking frames');
                    window.dispatchEvent(new CustomEvent('sakura-phone-companion-tracking',{detail:{enabled:true}}));
                    viewer.setCompanionTracking(true);viewer.setVtuberTrackingMode(true);viewer.setUserTracking(true);
                }else if(command.type==='companion-tracking-stop'){
                    remote=false;remoteKind='';viewer.setUserTracking(false);viewer.setVtuberTrackingMode(false);viewer.setCompanionTracking(false);
                    window.dispatchEvent(new CustomEvent('sakura-phone-companion-tracking',{detail:{enabled:false}}));
                }else if(command.type==='tracking-stop'){remote=false;remoteKind='';viewer.setUserTracking(false);}
                else if(command.type==='camera-start'||command.type==='camera-stop'){
                    if(command.type==='camera-start'){remote=false;if(remoteKind==='companion'){viewer.setVtuberTrackingMode(false);viewer.setCompanionTracking(false);window.dispatchEvent(new CustomEvent('sakura-phone-companion-tracking',{detail:{enabled:false}}));}remoteKind='';viewer.setUserTracking(false);}
                    window.dispatchEvent(new CustomEvent('sakura-phone-camera',{detail:command}));
                }
                else if(command.type==='calibrate')viewer.calibrateUserTracking();
                else if(command.type==='clear-expressions')viewer.clearManualExpression();
                else if(command.type==='expression'&&(viewer.allMorphNames||[]).includes(command.name)){
                    // A phone pick outranks whatever was selected on the PC: it
                    // replaces the previous manual expression and pauses the
                    // automatic reactions (the viewer predicate checks the map).
                    if(command.enabled===false){
                        viewer.manualExpressions?.delete(command.name);
                        if(viewer.manualExpression?.name===command.name)viewer.manualExpression=null;
                        viewer.live2d?.removeExpression(command.name);
                        for(const p of viewer.customExpressions?.[command.name]?.parameters||[])if(!viewer.live2d)viewer.setMorph(p.id,0);
                        viewer.setMorph(command.name,0);
                    }else{
                        viewer.clearManualExpression?.();
                        viewer.manualExpressions ||= new Map();
                        viewer.manualExpressions.set(command.name,1);viewer.manualExpression={name:command.name,weight:1};
                        const custom=viewer.customExpressions?.[command.name];
                        if(custom&&!viewer.live2d)for(const p of custom.parameters)viewer.setMorph(p.id,p.value);
                        else viewer.setMorph(command.name,1);
                        viewer.live2d?.setExpression(command.name,1);
                    }
                }else if(command.type==='phone-reply')onReply(command.text);
            }
            if(data.camera)window.dispatchEvent(new CustomEvent('sakura-phone-camera-frame',{detail:data.camera}));
            if(remote&&data.frame){
                data.frame.timestamp=performance.now();
                if(!data.frame.headPoseFiltered)data.frame.face=filter.update(data.frame.face,data.frame.timestamp);
                const handsOn=document.getElementById('tracking-hands-enabled')?.getAttribute('aria-pressed')==='true';
                viewer.updateUserTracking({...data.frame,hands:handsOn ? data.frame.hands : [],handTrackingEnabled:handsOn&&data.frame.handTrackingEnabled!==false});
                lastRemoteFrame=performance.now();remoteSamples++;
                const elapsed=lastRemoteFrame-remoteStarted;
                if(elapsed>=1000){
                    const fps=Math.round(remoteSamples*1000/elapsed);
                    const metrics=data.frame.trackingMetrics||{};
                    const source=Number.isFinite(metrics.processedFps)?` · phone inference ${Math.round(metrics.processedFps)} FPS`:'';
                    const camera=Number.isFinite(metrics.cameraFps)?` · camera ${Math.round(metrics.cameraFps)} FPS`:'';
                    trackingStatus(`Sakura Mobile · ${fps} received FPS${source}${camera} · ${data.frame.face?.matrix?'face tracked':'face not detected'} · ${(data.frame.hands||[]).length} hands`);
                    remoteSamples=0;remoteStarted=lastRemoteFrame;
                }
            }else if(remote&&performance.now()-lastRemoteFrame>600){
                trackingStatus('Sakura Mobile · waiting for fresh tracking frames');
                viewer.updateUserTracking({face:{landmarks:[],blendshapes:[],matrix:null},hands:[],pose:null,handTrackingEnabled:false});
            }
        }catch(error){status.textContent='Phone connection: '+error.message;}
        finally{busy=false;}
    }
    // Poll faster than the incoming tracking cadence so a single-slot mailbox
    // is not sampled at the same 60 Hz phase and intermittently skips frames.
    let stopped=false;
    const tick=async()=>{
        if(stopped)return;
        const started=performance.now();await poll();
        if(!stopped)setTimeout(tick,Math.max(1,(remote?8:100)-(performance.now()-started)));
    };
    void tick();window.addEventListener('pagehide',()=>{stopped=true;},{once:true});
}
