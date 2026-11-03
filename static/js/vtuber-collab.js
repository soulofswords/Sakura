const CODE_ALPHABET='ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
const MAX_PACKAGE_BYTES=300*1024*1024;
const CHUNK_BYTES=16*1024;

function makeRoomCode(){
    const bytes=crypto.getRandomValues(new Uint8Array(10));
    return Array.from(bytes,byte=>CODE_ALPHABET[byte%CODE_ALPHABET.length]).join('');
}

function capturePose(viewer){
    if(viewer?.live2d?.avatar){
        const core=viewer.live2d.avatar.internalModel.coreModel,ids=core?._model?.parameters?.ids||[];
        const parameters={};
        for(const id of ids){const value=core.getParameterValueById(id);if(Number.isFinite(value))parameters[id]=value;}
        return {kind:'live2d',parameters};
    }
    if(!viewer?.model)return null;
    const bones=[],morphs=[];
    viewer.model.traverse(node=>{
        if(node.isBone)bones.push({q:node.quaternion.toArray(),p:node.position.toArray()});
        if(node.isMesh&&node.morphTargetInfluences)morphs.push(Array.from(node.morphTargetInfluences,value=>Number.isFinite(value)?value:0));
    });
    return {kind:'3d',bones,morphs};
}

function selectedModelPath(viewer){
    const url=viewer?.lastModelUrl;
    if(!url)return '';
    const parsed=new URL(url,location.href);
    if(!parsed.pathname.startsWith('/models/'))return '';
    return decodeURIComponent(parsed.pathname.slice('/models/'.length));
}

export function installVtuberCollab({viewer,ModelViewer}){
    const dialog=document.getElementById('vtuber-collab-dialog');
    const open=document.getElementById('vtuber-collab-btn');
    const relayInput=document.getElementById('collab-relay-url');
    const roomInput=document.getElementById('collab-room-code');
    const turnUrl=document.getElementById('collab-turn-url');
    const turnUser=document.getElementById('collab-turn-user');
    const turnPassword=document.getElementById('collab-turn-password');
    const status=document.getElementById('vtuber-collab-status');
    const connectButton=document.getElementById('collab-connect');
    const disconnectButton=document.getElementById('collab-disconnect');
    const stage=document.getElementById('vtuber-collab-stage');
    const shared=document.createElement('section');shared.innerHTML='<h3>Shared conversation</h3><label><input data-shared-enabled type="checkbox"> Receive shared messages (not private history)</label><input data-shared-text maxlength="500" placeholder="Message to collaborators" aria-label="Shared collab message"><button data-shared-send type="button">Send to room</button><button data-shared-use type="button">Use these messages with my next Companion question</button><p data-shared-status></p><div data-shared-log></div>';
    dialog.querySelector('.collab-dialog-card')?.append(shared);
    const sharedEl=name=>shared.querySelector('[data-shared-'+name+']');let sharedMessages=[];
    function sharedMessage(speaker,text){if(!sharedEl('enabled').checked)return;const row={speaker:String(speaker).slice(0,60),text:String(text).slice(0,500)};sharedMessages.push(row);sharedMessages=sharedMessages.slice(-12);const line=document.createElement('p');line.textContent=row.speaker+': '+row.text;sharedEl('log').append(line);while(sharedEl('log').children.length>12)sharedEl('log').firstChild.remove();}
    sharedEl('send').onclick=()=>{const text=sharedEl('text').value.trim();if(!text)return;sharedEl('enabled').checked=true;sharedMessage('Me',text);let sent=0;for(const peer of peers.values())if(peer.control?.readyState==='open'){peer.control.send(JSON.stringify({type:'shared-chat',text}));sent++;}sharedEl('status').textContent=sent?'Sent to '+sent+' connected collaborators.':'No collaborator is connected; message is local only.';sharedEl('text').value='';};
    sharedEl('use').onclick=()=>{if(window.SAKURA_EDITION==='vtuber'){sharedEl('status').textContent='Standalone VTuber has no chat AI. Use Companion for shared-context questions.';return;}window.sakuraSharedContext=sharedMessages.slice(-6);fetch('/api/features/shared-context',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:window.sakuraSharedContext})}).then(async response=>{const data=await response.json();sharedEl('status').textContent=response.ok?'Shared quotes are available to Companion and the reviewed Agent context tool.':(data.detail||'Enable shared context in Agent → Memory workshop first.');}).catch(error=>sharedEl('status').textContent=error.message);};
    sharedEl('enabled').onchange=()=>{if(!sharedEl('enabled').checked){sharedMessages=[];window.sakuraSharedContext=[];sharedEl('log').replaceChildren();if(window.SAKURA_EDITION!=='vtuber')fetch('/api/features/shared-context',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[]})}).catch(()=>{});}};
    const peers=new Map();
    let socket=null,peerId='',poseTimer=null,localSeat=null,originalViewerParent=null,originalViewerNext=null,originalViewerStyle='';

    try{relayInput.value=localStorage.getItem('sakura_collab_relay')||'';}catch(_){}
    const updateButtons=()=>{connectButton.disabled=!!socket;disconnectButton.disabled=!socket;};
    const signal=(type,to,data)=>{if(socket?.readyState===WebSocket.OPEN)socket.send(JSON.stringify({type,to,data}));};
    const say=text=>{status.textContent=text;};
    const enterStage=()=>{
        stage.hidden=false;
        if(!localSeat){
            originalViewerParent=viewer.container.parentNode;originalViewerNext=viewer.container.nextSibling;originalViewerStyle=viewer.container.getAttribute('style')||'';
            localSeat=document.createElement('section');localSeat.className='collab-avatar-seat';localSeat.dataset.peer=peerId;
            const label=document.createElement('span');label.className='collab-avatar-label';label.textContent='You';localSeat.append(label);
            stage.append(localSeat);localSeat.append(viewer.container);
            viewer.container.style.cssText='position:absolute;inset:0;width:100%;height:100%;z-index:1;';
        }
        requestAnimationFrame(()=>{viewer.onResize?.();for(const state of peers.values())state.modelViewer?.onResize?.();});
    };
    const leaveStage=()=>{
        for(const state of peers.values()){
            state.modelViewer?.destroy?.();state.seat?.remove();
        }
        peers.clear();
        if(localSeat){
            if(originalViewerParent){originalViewerParent.insertBefore(viewer.container,originalViewerNext?.parentNode===originalViewerParent?originalViewerNext:null);}
            viewer.container.setAttribute('style',originalViewerStyle);localSeat.remove();localSeat=null;
        }
        stage.hidden=true;document.body.classList.remove('vtuber-collab-active');
        requestAnimationFrame(()=>viewer?.onResize?.());
    };

    async function sendModel(state){
        if(state.packageSent||!state.control?.open)return;
        const path=selectedModelPath(viewer);
        if(!path){say('Load a model from Sakura’s model library before joining Collab.');return;}
        state.packageSent=true;state.currentModelPath=path;say('Preparing your model for '+state.peerId+'…');
        try{
            const response=await fetch('/api/collab/package',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path})});
            if(!response.ok){const body=await response.json().catch(()=>({}));throw Error(body.error||'Could not package your model.');}
            const zip=await response.arrayBuffer();
            if(zip.byteLength>MAX_PACKAGE_BYTES)throw Error('Model package exceeds the 300 MB session limit.');
            const entry=decodeURIComponent(response.headers.get('X-Sakura-Collab-Entry')||path.split('/').pop());
            state.control.send(JSON.stringify({type:'package-start',size:zip.byteLength,entry,name:decodeURIComponent(response.headers.get('X-Sakura-Collab-Name')||entry)}));
            for(let offset=0;offset<zip.byteLength;offset+=CHUNK_BYTES){
                while(state.control.bufferedAmount>1024*1024)await new Promise(resolve=>setTimeout(resolve,20));
                state.control.send(zip.slice(offset,Math.min(zip.byteLength,offset+CHUNK_BYTES)));
            }
            state.control.send(JSON.stringify({type:'package-end'}));
            say('Sending your model to '+state.peerId+'…');
        }catch(error){state.packageSent=false;say('Model share failed: '+error.message);}
    }

    async function importSharedModel(state){
        const received=state.received;
        if(!received)return;
        state.received=null;
        const size=received.parts.reduce((total,part)=>total+part.byteLength,0);
        if(size!==received.size){say('The model transfer was incomplete.');return;}
        say('Installing a temporary copy of '+received.name+'…');
        try{
            const buffer=new Uint8Array(size);let offset=0;for(const part of received.parts){buffer.set(new Uint8Array(part),offset);offset+=part.byteLength;}
            const response=await fetch('/api/collab/import',{method:'POST',headers:{'Content-Type':'application/zip','X-Sakura-Collab-Entry':encodeURIComponent(received.entry)},body:buffer});
            const result=await response.json();if(!response.ok||!result.ok)throw Error(result.error||'Could not import the shared model.');
            let remote=state.modelViewer;
            if(!remote){
                const seat=document.createElement('section');seat.className='collab-avatar-seat';seat.dataset.peer=state.peerId;
                const label=document.createElement('span');label.className='collab-avatar-label';label.textContent=state.peerId.slice(0,8)+' · '+received.name;seat.append(label);stage.append(seat);
                const container=document.createElement('div');container.className='collab-remote-viewer';container.id='collab-viewer-'+state.peerId.replace(/[^a-zA-Z0-9_-]/g,'_');seat.append(container);
                remote=new ModelViewer(container.id);remote.areAiExpressionsAutomatic=()=>false;remote.userTracking=false;remote.vtuberTrackingMode=true;
                state.seat=seat;state.modelViewer=remote;state.label=label;
            }else{
                if(state.tempModelToken)void fetch('/api/collab/import/'+encodeURIComponent(state.tempModelToken),{method:'DELETE'}).catch(()=>{});
                state.label.textContent=state.peerId.slice(0,8)+' · '+received.name;
            }
            const loaded=await remote.loadModel(result.model_url);
            if(!loaded)throw Error('Sakura could not load the collaborator’s avatar.');
            state.tempModelToken=result.model_url.split('/')[2];state.ready=true;requestAnimationFrame(()=>remote.onResize?.());say('Shared avatar loaded · '+(peers.size+1)+' participants.');
        }catch(error){say('Could not load shared avatar: '+error.message);state.received=null;}
    }

    async function receiveControl(state,event){
        if(typeof event.data!=='string'){
            if(state.received){state.received.parts.push(event.data);state.received.receivedBytes+=event.data.byteLength;}
            return;
        }
        if(typeof event.data!=='string'||event.data.length>10000)return;let message;try{message=JSON.parse(event.data);}catch(_){return;}
        if(message.type==='shared-chat'){const now=Date.now();if(now-(state.sharedAt||0)<500)return;state.sharedAt=now;if(typeof message.text==='string'&&message.text.length<=500)sharedMessage(state.peerId,message.text);return;}
        if(message.type==='package-start'){
            if(!Number.isSafeInteger(message.size)||message.size<=0||message.size>MAX_PACKAGE_BYTES){say('The collaborator model exceeds Sakura’s 300 MB limit.');return;}
            state.received={size:message.size,entry:String(message.entry||''),name:String(message.name||'Avatar'),parts:[],receivedBytes:0};
            say('Receiving '+state.received.name+' from '+state.peerId+'…');
        }else if(message.type==='package-end')await importSharedModel(state);
    }

    function makePeer(remoteId,initiator){
        if(peers.has(remoteId))return peers.get(remoteId);
        const peer=new RTCPeerConnection({iceServers:[{urls:'stun:stun.l.google.com:19302'},...(turnUrl.value.trim()?[{urls:turnUrl.value.trim(),username:turnUser.value.trim(),credential:turnPassword.value}]:[])]});
        const state={peerId:remoteId,peer,control:null,pose:null,pendingIce:[],modelViewer:null,seat:null,ready:false,packageSent:false,received:null};peers.set(remoteId,state);
        peer.onicecandidate=event=>{if(event.candidate)signal('ice',remoteId,event.candidate.toJSON());};
        peer.onconnectionstatechange=()=>{if(['failed','closed'].includes(peer.connectionState)){removePeer(remoteId,'A participant disconnected.');}};
        const installChannel=(channel)=>{
            if(channel.label==='sakura-control'){
                state.control=channel;channel.binaryType='arraybuffer';
                channel.onopen=()=>void sendModel(state);
                channel.onmessage=event=>void receiveControl(state,event);
            }else if(channel.label==='sakura-pose'){
                state.pose=channel;channel.binaryType='arraybuffer';
                channel.onmessage=event=>{
                    try{const data=JSON.parse(typeof event.data==='string'?event.data:new TextDecoder().decode(event.data));state.modelViewer?.setCollaboratorPose(data);}catch(_){}
                };
            }
        };
        peer.ondatachannel=event=>installChannel(event.channel);
        if(initiator){
            installChannel(peer.createDataChannel('sakura-control'));
            installChannel(peer.createDataChannel('sakura-pose',{ordered:false,maxRetransmits:0}));
            void peer.createOffer().then(offer=>peer.setLocalDescription(offer)).then(()=>signal('offer',remoteId,peer.localDescription)).catch(error=>say('Could not start peer connection: '+error.message));
        }
        return state;
    }

    async function acceptSignal(message){
        const remoteId=message.from;if(!remoteId)return;
        if(message.type==='peer_left'){removePeer(remoteId,'A participant disconnected.');return;}
        const state=makePeer(remoteId,false),peer=state.peer;
        if(message.type==='offer'){
            await peer.setRemoteDescription(message.data);for(const candidate of state.pendingIce.splice(0))await peer.addIceCandidate(candidate);
            const answer=await peer.createAnswer();await peer.setLocalDescription(answer);signal('answer',remoteId,peer.localDescription);
        }else if(message.type==='answer'){
            await peer.setRemoteDescription(message.data);for(const candidate of state.pendingIce.splice(0))await peer.addIceCandidate(candidate);
        }else if(message.type==='ice'&&message.data){if(peer.remoteDescription)await peer.addIceCandidate(message.data);else state.pendingIce.push(message.data);}
    }

    function removePeer(remoteId,message='Disconnected.'){
        const state=peers.get(remoteId);if(!state)return;
        state.peer.close();state.modelViewer?.destroy?.();state.seat?.remove();
        if(state.tempModelToken)void fetch('/api/collab/import/'+encodeURIComponent(state.tempModelToken),{method:'DELETE'}).catch(()=>{});
        peers.delete(remoteId);say(message+' '+(peers.size+1)+' participants remain.');
    }

    function teardown(message='Disconnected.'){
        if(poseTimer){clearInterval(poseTimer);poseTimer=null;}
        for(const state of peers.values()){state.peer.close();state.modelViewer?.destroy?.();if(state.tempModelToken)void fetch('/api/collab/import/'+encodeURIComponent(state.tempModelToken),{method:'DELETE'}).catch(()=>{});}
        peers.clear();
        if(socket){const old=socket;socket=null;old.close();}
        leaveStage();say(message);updateButtons();
    }

    open?.addEventListener('click',()=>{if(!document.body.classList.contains('tracking-only'))return;dialog.showModal();});
    document.getElementById('collab-close').addEventListener('click',()=>dialog.close());
    document.getElementById('collab-generate-room').addEventListener('click',()=>{roomInput.value=makeRoomCode();roomInput.select();});
    document.getElementById('collab-copy-room').addEventListener('click',async()=>{
        if(!roomInput.value.trim()){say('Create or enter a room code first.');return;}
        try{await navigator.clipboard.writeText(roomInput.value.trim());say('Room code copied. Send it to your collaborators.');}
        catch(_){roomInput.select();say('Room code selected. Copy it and send it to your collaborators.');}
    });
    document.getElementById('collab-disconnect').addEventListener('click',()=>teardown());
    dialog.addEventListener('cancel',()=>teardown());

    connectButton.addEventListener('click',async()=>{
        if(!document.body.classList.contains('tracking-only')){say('Switch to VTuber mode before starting a collab.');return;}
        if(!selectedModelPath(viewer)){say('Load a model before starting a collab.');return;}
        if(!confirm('Collab will send a temporary copy of your selected model files and live movement to each person in the room. Continue?'))return;
        const base=relayInput.value.trim().replace(/\/+$/,''),room=roomInput.value.trim();
        let protocol='',host='';try{const parsed=new URL(base);protocol=parsed.protocol;host=parsed.hostname;}catch(_){}
        if(protocol!=='wss:'&&!(protocol==='ws:'&&['localhost','127.0.0.1'].includes(host))){say('Enter a secure WSS relay URL (wss://…). Local ws:// is allowed only for localhost tests.');return;}
        if(!/^[A-Za-z0-9_-]{8,32}$/.test(room)){say('Enter a valid room code or create one.');return;}
        try{localStorage.setItem('sakura_collab_relay',base);}catch(_){}
        peerId=crypto.randomUUID();connectButton.disabled=true;say('Connecting to the Collab relay…');
        socket=new WebSocket(`${base}/ws/${encodeURIComponent(room)}`);
        socket.onopen=()=>socket.send(JSON.stringify({type:'join',peer:peerId}));
        socket.onmessage=event=>{
            try{const message=JSON.parse(event.data);
                if(message.type==='joined'){
                    enterStage();poseTimer=setInterval(()=>{
                        const path=selectedModelPath(viewer),pose=capturePose(viewer);
                        for(const state of peers.values()){
                            if(path&&state.currentModelPath!==path&&state.control?.readyState==='open'){state.packageSent=false;void sendModel(state);}
                            if(pose&&state.pose?.readyState==='open'){const bytes=new TextEncoder().encode(JSON.stringify(pose));if(bytes.byteLength<60000)state.pose.send(bytes);}
                        }
                    },50);
                    say(message.peers?.length?'Joined room · syncing '+message.peers.length+' participant(s)…':'Room ready · waiting for collaborators…');dialog.close();return;
                }
                if(message.type==='peer_joined'){
                    if(peers.size>=5){say('Room is full. Sakura supports up to six participants.');return;}
                    makePeer(message.peer,true);say('A participant joined · syncing avatars…');return;
                }
                if(message.type==='room_full'){teardown('This room already has six participants.');return;}
                void acceptSignal(message).catch(error=>say('Collab sync failed: '+error.message));
            }catch(error){say('Invalid relay response: '+error.message);}
        };
        socket.onerror=()=>say('Could not reach the relay. Check the WSS URL and that the relay is deployed.');
        socket.onclose=()=>{if(socket)teardown('Collab relay disconnected.');};
        updateButtons();
    });

    window.addEventListener('pagehide',()=>teardown());
    window.addEventListener('sakura-vtuber-mode-off',()=>teardown('VTuber mode ended.'));
}
