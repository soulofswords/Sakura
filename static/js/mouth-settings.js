export function installMouthSettings(getViewer,getKey,getMic=()=> '') {
    const source=document.getElementById('mouth-source'),status=document.getElementById('mouth-status');
    const combinedToggle=document.getElementById('mouth-combined-enabled');
    const defaults={source:'webcam',gain:1,cutoff:.01,smoothing:.08,mode:'simple',mapping:{}};
    let config={...defaults,mapping:{}},stream=null,context=null,frame=null,generation=0;
    const storage=()=> 'sakura_mouth:'+getKey();
    const controls={gain:document.getElementById('mouth-gain'),cutoff:document.getElementById('mouth-cutoff'),smoothing:document.getElementById('mouth-smoothing')};
    const apply=()=>{
        const v=getViewer();if(!v)return;
        v.mouthOptions=config;
        v.setTrackingMouthEnabled?.(['webcam','both'].includes(config.source)&&!v.voiceChangerActive);
        combinedToggle.checked=config.source==='both'&&Boolean(stream);
        localStorage.setItem(storage(),JSON.stringify(config));
    };
    async function stop(){++generation;if(frame)cancelAnimationFrame(frame);frame=null;stream?.getTracks().forEach(t=>t.stop());stream=null;combinedToggle.checked=false;const v=getViewer();if(v)v.microphoneMouthWeights=null;const old=context;context=null;await old?.close().catch(()=>{});v?.resetMouth();status.textContent='Microphone lip sync stopped.';}
    const refresh=()=>{
        void stop();try{const saved=JSON.parse(localStorage.getItem(storage())||'{}');config={...defaults,...saved,mapping:{...(saved.mapping||{})}};}catch(_){config={...defaults,mapping:{}};}
        source.value=config.source;document.getElementById('mouth-method').value=config.mode;
        for(const [key,input]of Object.entries(controls))input.value=config[key];
        const list=document.getElementById('mouth-mapping');list.replaceChildren();
        for(const vowel of ['A','I','U','E','O']){
            const label=document.createElement('label');label.textContent=vowel+' shape';const select=document.createElement('select');
            select.add(new Option('Automatic', ''));select.add(new Option('Disabled','none'));
            const names=getViewer()?.live2d?Array.from(getViewer().live2d.avatar.internalModel.coreModel._model.parameters.ids):getViewer()?.allMorphNames||[];
            names.forEach(name=>select.add(new Option(name,name)));select.value=config.mapping[vowel]||'';
            select.onchange=()=>{getViewer()?.resetMouth();config.mapping[vowel]=select.value;apply();};label.append(select);list.append(label);
        }apply();
    };
    source.onchange=()=>{void stop();config.source=source.value;apply();};
    combinedToggle.onchange=async()=>{
        if(combinedToggle.checked){
            config.source='both';source.value='both';
            await document.getElementById('mouth-mic-start').onclick();
            if(stream&&!getViewer()?.userTracking)document.getElementById('settings-start-tracking')?.click();
        }else{await stop();config.source='off';source.value='off';apply();}
    };
    document.getElementById('mouth-method').onchange=e=>{config.mode=e.target.value;apply();};
    for(const [key,input]of Object.entries(controls))input.oninput=()=>{config[key]=Number(input.value);apply();};
    document.getElementById('mouth-mic-stop').onclick=async()=>{await stop();config.source='off';source.value=config.source;apply();};
    document.getElementById('mouth-reset').onclick=()=>{localStorage.removeItem(storage());refresh();};
    document.getElementById('mouth-mic-start').onclick=async()=>{
        const desiredSource=config.source==='both'?'both':'microphone';
        await stop();const token=generation;
        if(getViewer()?.voiceChangerActive){status.textContent='Voice changer already controls the mouth from its output. Turn it off for direct microphone lip sync.';return;}
        try{
            const acquired=await navigator.mediaDevices.getUserMedia({audio:{...(getMic()?{deviceId:{exact:getMic()}}:{}),echoCancellation:true,noiseSuppression:true}});
            if(token!==generation){acquired.getTracks().forEach(t=>t.stop());return;}
            stream=acquired;context=new (window.AudioContext||window.webkitAudioContext)();await context.resume();
            const analyser=context.createAnalyser();analyser.fftSize=1024;context.createMediaStreamSource(stream).connect(analyser);
            const time=new Float32Array(1024),frequency=new Uint8Array(analyser.frequencyBinCount);let last=performance.now(),level=0;
            source.value=config.source=desiredSource;apply();status.textContent='Microphone lip sync on. Audio is analyzed locally; no playback or AI reply.';
            const loop=()=>{
                if(token!==generation)return;const now=performance.now(),dt=Math.min(.1,(now-last)/1000);last=now;
                analyser.getFloatTimeDomainData(time);let power=0;for(const n of time)power+=n*n;
                const target=Math.min(1,Math.max(0,Math.sqrt(power/time.length)-config.cutoff)*config.gain*8);
                level+=(target-level)*(1-Math.exp(-dt/Math.max(.01,config.smoothing)));
                const weights={A:level,I:0,U:0,E:0,O:0};
                if(config.mode==='spectral'){
                    analyser.getByteFrequencyData(frequency);const bands=[[200,500,'O'],[500,900,'A'],[900,1600,'E'],[1600,2500,'I'],[100,200,'U']];let best=-1,vowel='A';
                    for(const [low,high,key]of bands){let sum=0,count=0;for(let hz=low;hz<high;hz+=context.sampleRate/1024){sum+=frequency[Math.min(frequency.length-1,Math.floor(hz*1024/context.sampleRate))];count++;}if(sum/count>best){best=sum/count;vowel=key;}}
                    weights.A=0;weights[vowel]=level;
                }
                const viewer=getViewer();if(viewer)viewer.microphoneMouthWeights=weights;
                if(!viewer?.audioPlaybackActive&&(config.source!=='both'||!viewer?.userTracking))viewer?.setVowelWeights(weights);frame=requestAnimationFrame(loop);
            };loop();
        }catch(error){await stop();status.textContent=error.message;}
    };
    window.addEventListener('pagehide',()=>{void stop();});return {refresh,stop};
}
