export function updateLocalModelChoices(data) {
    const models=data.models||[],native=data.native_models||[];
    const game=document.getElementById('ollama-model-options');
    game?.replaceChildren(...models.map(item=>new Option(item.name,item.name)));
    const universal=document.getElementById('universal-model-options');
    universal?.replaceChildren(...models.map(item=>new Option(item.name,item.name)),...native.map(item=>new Option(item.label+' · '+item.engine,item.name)));
    const button=document.getElementById('qwen-native-btn');
    const qwen=native.find(item=>item.engine==='colibri'&&/qwen.*3[.]6/i.test(item.label));
    const requirements=document.getElementById('native-model-requirements');
    if(requirements)requirements.hidden=!qwen;
    if(button){button.hidden=!qwen;button.onclick=()=>{
        if(!qwen)return;
        document.getElementById('ollama-model').value=qwen.name;
        document.getElementById('ollama-scan-status').textContent='Selected '+qwen.label+'. Save AI settings to activate it. Screen images still use your vision model.';
    };}
}

export function installLocalModelManager() {
    const choice=document.getElementById('local-download-choice'),name=document.getElementById('local-download-name');
    const specs=document.getElementById('local-download-specs'),status=document.getElementById('local-download-status');
    const installed=document.getElementById('local-uninstall-choice'),download=document.getElementById('local-download-start');
    const search=document.getElementById('local-model-search'),families=document.getElementById('local-model-family');
    let catalog=[],timer=null,wasRunning=false,searchTimer=null,searchGeneration=0,tagGeneration=0;
    function showModels(models){
        catalog=models;choice.replaceChildren(...models.map(item=>new Option(item.name+' · '+(item.download||'Vision'),item.model)));
        choice.dispatchEvent(new Event('change'));
    }
    async function findModels(){
        const generation=++searchGeneration;
        status.textContent='Searching Ollama vision models…';
        try{
            const data=await request('/api/ollama/manager/search',{query:search.value.trim()});
            if(generation!==searchGeneration)return;
            families.replaceChildren(new Option('Choose a model family',''),...data.models.map(item=>new Option(item.name,item.family)));
            status.textContent=data.models.length?'Select a family to see its downloadable weights.':'No vision families found. You can still enter an exact Ollama model name.';
        }catch(error){if(generation===searchGeneration)status.textContent='Search unavailable · '+error.message;}
    }
    search.addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(findModels,400);});
    search.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();clearTimeout(searchTimer);findModels();}});
    document.getElementById('local-model-search-btn').onclick=()=>{clearTimeout(searchTimer);findModels();};
    families.onchange=async()=>{
        const generation=++tagGeneration;if(!families.value)return;
        status.textContent='Loading weight variants…';
        try{const data=await request('/api/ollama/manager/search',{family:families.value});if(generation!==tagGeneration)return;
            showModels(data.models);status.textContent=data.models.length?'Choose the parameter size and quantization, then Download.':'No downloadable image-capable variants were found.';
        }catch(error){if(generation===tagGeneration)status.textContent=error.message;}
    };
    const folder=()=>document.getElementById('ollama-models-folder').value.trim();
    async function request(url,payload) {
        const response=await fetch(url,payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
        const data=await response.json();if(!response.ok)throw Error(data.error||'Model operation failed.');return data;
    }
    async function refresh() {
        const data=await request('/api/ollama/models',{folder:folder()});
        // Keep the selector clean with older running backends too.
        const publicNames=new Set(data.models.filter(m=>!m.name.startsWith('llamacpp:')).map(m=>m.name));
        const clean=new Map();
        for(const item of data.models){
            if(/^llamacpp:[0-9a-f]{64}$/i.test(item.name)&&publicNames.size)continue;
            if(!clean.has(item.name)||item.size>clean.get(item.name).size)clean.set(item.name,item);
        }
        data.models=[...clean.values()];
        installed.replaceChildren(...data.models.map(item=>new Option(`${item.name} · ${(item.size/1e9).toFixed(1)} GB`,item.name)));
        updateLocalModelChoices(data);
    }
    async function poll() {
        try {
            const data=await request('/api/ollama/manager');
            if(!catalog.length){
                showModels(data.catalog);
            }
            download.disabled=data.job.running;
            if(data.job.running||wasRunning)status.textContent=data.job.message+(data.job.running&&data.job.percent!==null?` (${data.job.percent}%)`:'');
            if(wasRunning&&!data.job.running)await refresh();
            wasRunning=data.job.running;
        }catch(error){status.textContent=error.message;}
        finally{timer=setTimeout(poll,2000);}
    }
    choice.onchange=()=>{
        const model=catalog.find(item=>item.model===choice.value);if(!model)return;
        name.value=model.model;if(!model.ram_gb){specs.textContent=`Vision · Weights: ${model.model} · Download ${model.download}. Allow extra RAM/VRAM for context, images, the avatar and your game. Larger quantizations use more memory.`;return;}specs.textContent=`Recommended: ${model.ram_gb} GB RAM / ${model.vram_gb} GB VRAM. Download ${model.download}; allow ${model.disk_gb} GB free disk. Estimates vary with context, images, avatar and other apps.`;
    };
    download.onclick=async()=>{
        download.disabled=true;
        try{const data=await request('/api/ollama/manager/download',{model:name.value.trim(),folder:folder()});wasRunning=true;status.textContent=data.message;}
        catch(error){status.textContent=error.message;download.disabled=false;}
    };
    document.getElementById('local-model-refresh').onclick=()=>refresh().catch(e=>status.textContent=e.message);
    document.getElementById('local-model-use').onclick=async()=>{
        if(!installed.value)return;
        document.getElementById('ollama-model').value=installed.value;
        try{const info=await request('/api/ollama/manager/details',{model:installed.value,folder:folder()});status.textContent=`Selected ${installed.value} · ${info.vision?'Vision verified':'Text only; keep an installed vision model for images'}. Save AI settings to activate it.`;}catch(error){status.textContent=error.message;}
    };
    document.getElementById('local-model-uninstall').onclick=async()=>{
        const model=installed.value;if(!model)return;
        if(!window.confirm(`Uninstall ${model} from the selected Ollama model store? You can download it again later. Other models will be kept.`))return;
        try{const data=await request('/api/ollama/manager/delete',{model,folder:folder(),confirm:model});status.textContent=data.message;await refresh();}
        catch(error){status.textContent=error.message;}
    };
    document.getElementById('local-gguf-browse').onclick=async()=>{
        try{const paths=await window.pywebview?.api.choose_local_gguf_files();if(paths?.length)document.getElementById('local-gguf-paths').value=paths.join('\n');}
        catch(error){status.textContent='Enter the GGUF file paths below. '+error.message;}
    };
    document.getElementById('local-gguf-import').onclick=async()=>{
        try{const data=await request('/api/ollama/manager/import',{model:document.getElementById('local-gguf-name').value.trim(),paths:document.getElementById('local-gguf-paths').value.split(/\r?\n/).map(v=>v.trim()).filter(Boolean),folder:folder()});wasRunning=true;status.textContent=data.message;}
        catch(error){status.textContent=error.message;}
    };
    refresh().catch(()=>{});poll();window.addEventListener('pagehide',()=>clearTimeout(timer),{once:true});
}
