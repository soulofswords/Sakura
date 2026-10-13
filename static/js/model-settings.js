import {ModelMaterials,storedRemap} from './model-materials.js?v=opacity-boost3';
import {installColorDial} from './color-dial.js?v=1';
import {installMouthSettings} from './mouth-settings.js?v=chat-reader-mouth4';
import {installLive2DFaceMapping} from './live2d-face-mapping.js?v=1';
import {installBoneSettings} from './model-bones.js?v=snapshot4';

export function installModelSettings(getViewer,getModelKey,refreshPmx,getMic) {
    const zoom=document.getElementById('model-settings-zoom');
    const applyZoom=value=>{getViewer()?.setDisplaySize(value);zoom.value=Math.round((getViewer()?.camera.zoom||1)*100);};
    document.getElementById('model-settings-zoom-in').onclick=()=>applyZoom((getViewer()?.camera.zoom||1)*110);
    document.getElementById('model-settings-zoom-out').onclick=()=>applyZoom((getViewer()?.camera.zoom||1)*100/1.1);
    document.getElementById('model-settings-zoom-reset').onclick=()=>applyZoom(100);
    zoom.onchange=()=>applyZoom(Number(zoom.value));
    window.addEventListener('wheel',event=>{
        if(!document.body.classList.contains('model-part-picking')&&!document.body.classList.contains('picking-model-part'))return;
        if(event.target.closest?.('#expression-modal .modal-card'))return;
        event.preventDefault();event.stopImmediatePropagation();
        applyZoom((getViewer()?.camera.zoom||1)*100*Math.exp(-Math.max(-200,Math.min(200,event.deltaY))*.002));
    },{capture:true,passive:false});
    const bones=installBoneSettings(getViewer,getModelKey);
    const lighting=document.getElementById('model-lighting-controls');
    for(const id of ['character-glow-slider','light-angle-slider','light-elevation-slider','gloss-boost-slider']){
        const group=document.getElementById(id)?.closest('.slider-group');if(group)lighting.append(group);
    }
    const envPicker=document.getElementById('env-color-picker');
    if(envPicker)installColorDial(envPicker,document.getElementById('env-color-dial'));
    const backgroundPicker=document.getElementById('obs-background-color');
    if(backgroundPicker)installColorDial(backgroundPicker,document.getElementById('obs-background-dial'));
    const mouth=installMouthSettings(getViewer,getModelKey,getMic);
    const faceMapping=installLive2DFaceMapping(getViewer,getModelKey);
    const panel=document.getElementById('expression-modal'),status=document.getElementById('model-material-status');
    const part=document.getElementById('model-color-part'),texture=document.getElementById('model-remap-part');
    const picker=document.getElementById('model-color'),strength=document.getElementById('model-color-strength');
    const opacity=document.getElementById('model-color-opacity');
    const dial=installColorDial(picker,document.getElementById('model-color-dial'));
    const file=document.getElementById('model-remap-file');
    const pmx=document.getElementById('pmx-texture-selector');
    document.getElementById('model-remapping-panel').append(pmx);
    let controller=null,root=null,modelKey='',revision=0,activeTab='coloring',busy=false;
    const storageKey=()=> 'sakura_model_colors:'+modelKey;
    const saveColors=()=>localStorage.setItem(storageKey(),JSON.stringify(controller.colors));
    const tab=name=>{
        if(name==='mouth'&&!getViewer()?.vtuberTrackingMode)name='coloring';
        activeTab=name;
        document.querySelectorAll('[data-model-tab]').forEach(button=>{const selected=button.dataset.modelTab===name;button.classList.toggle('active',selected);button.setAttribute('aria-selected',String(selected));});
        document.querySelectorAll('[data-model-panel]').forEach(section=>section.hidden=section.dataset.modelPanel!==name);
    };
    document.querySelectorAll('[data-model-tab]').forEach(button=>button.onclick=()=>tab(button.dataset.modelTab));
    const updateColor=()=>{const config=controller?.colors[part.value];picker.value=config?.color||'#ffffff';strength.value=Math.round((config?.strength??1)*100);opacity.value=Math.round((1-(config?.opacity??1))*100);document.getElementById('model-color-opacity-value').textContent=opacity.value+'%';document.getElementById('model-color-strength-value').textContent=strength.value+'%';dial.sync();};
    part.onchange=updateColor;
    strength.oninput=()=>document.getElementById('model-color-strength-value').textContent=strength.value+'%';
    opacity.oninput=()=>document.getElementById('model-color-opacity-value').textContent=opacity.value+'%';
    const fill=(select,entries)=>{const previous=select.value;select.replaceChildren();entries.forEach(e=>select.add(new Option(e.name,e.id)));if(entries.some(e=>e.id===previous))select.value=previous;select.disabled=!entries.length;};
    const refresh=async()=>{
        zoom.value=Math.round((getViewer()?.camera.zoom||1)*100);
        bones.refresh();
        const viewer=getViewer(),identity=viewer?.live2d||viewer?.model,key=getModelKey();
        const tracking=!!viewer?.vtuberTrackingMode;
        faceMapping.refresh();
        document.querySelector('[data-model-tab="mouth"]').hidden=!tracking;
        if(!tracking){mouth.stop();if(activeTab==='mouth')tab('coloring');}
        if(!identity){status.textContent='Load a model to customize its appearance.';return;}
        if(root!==identity||key!==modelKey){
            stopPicking();
            mouth.refresh();
            const generation=++revision;root=identity;modelKey=key;
            controller=new ModelMaterials(viewer);viewer.materialEditor=controller;controller.attach(key);
            const current=controller;
            let colors={};try{const saved=JSON.parse(localStorage.getItem(storageKey())||'{}');if(saved&&typeof saved==='object'&&!Array.isArray(saved))colors=saved;}catch(_){}
            for(const entry of current.remapTargets()){
                try{const saved=await storedRemap(key,entry.id);if(generation!==revision||root!==(getViewer()?.live2d||getViewer()?.model))return;if(saved)await current.setRemap(entry.id,saved);}
                catch(error){status.textContent=error.message;}
            }
            if(generation!==revision)return;
            for(const [id,config]of Object.entries(colors))try{current.setColor(id,config);}catch(error){status.textContent=error.message;}
        }
        fill(part,controller.colorTargets());fill(texture,controller.remapTargets());updateColor();
        document.getElementById('model-color-hint').textContent=viewer.live2d
            ? 'Choose a Live2D ArtMesh to tint. Names come from the imported rig. Tint preserves its masks and transparency.'
            : 'Choose a material for hair, clothing or another part. Coloring preserves texture detail and transparency.';
        document.getElementById('model-remap-hint').textContent=viewer.live2d
            ? 'Replace a texture atlas with an image using the same UV layout. One atlas can contain several body parts.'
            : 'Replace the diffuse image for a material. Use a texture designed for this model’s UV layout.';
        document.getElementById('model-expression-hint').textContent=viewer.vtuberTrackingMode?'Preview imported expressions and assign their hotkeys.':'Expression previews and hotkeys are enabled in VTuber mode.';
        await refreshPmx?.();
    };
    const button=document.getElementById('expression-editor-btn'),original=button.onclick;
    button.onclick=()=>{original?.();tab(activeTab);status.textContent='';void refresh().catch(error=>status.textContent=error.message);};
    async function action(work){if(busy||!controller)return;busy=true;const current=controller,generation=revision;
        document.querySelectorAll('[data-material-action]').forEach(b=>b.disabled=true);
        try{await work(current);if(generation===revision)status.textContent='Saved for this model. Original model files are unchanged.';}
        catch(error){status.textContent=error.message;}
        finally{busy=false;document.querySelectorAll('[data-material-action]').forEach(b=>b.disabled=false);}
    }
    document.getElementById('model-color-apply').onclick=()=>action(async current=>{current.setHover(null);current.setColor(part.value,{color:picker.value,strength:Number(strength.value)/100,opacity:1-Number(opacity.value)/100});saveColors();});
    document.getElementById('model-color-reset').onclick=()=>action(async current=>{current.setColor(part.value,null);saveColors();updateColor();});
    document.getElementById('model-remap-apply').onclick=()=>action(async current=>{
        const blob=file.files[0];if(!blob)throw Error('Choose a PNG, JPG or WebP replacement image first.');
        const id=texture.value,key=modelKey;await current.setRemap(id,blob);await storedRemap(key,id,blob);file.value='';
    });
    document.getElementById('model-remap-reset').onclick=()=>action(async current=>{const id=texture.value;await current.setRemap(id,null);await storedRemap(modelKey,id,null);});
    let picking=false,lastHover=0;
    const pickButton=document.getElementById('model-pick-part');
    const stopPicking=()=>{picking=false;document.body.classList.remove('model-part-picking');controller?.setHover(null);const viewer=getViewer();if(viewer?.controls)viewer.controls.enabled=true;pickButton.textContent='Pick part on model';};
    pickButton.onclick=()=>{if(picking){stopPicking();return;}if(!controller)return;tab('coloring');picking=true;document.body.classList.add('model-part-picking');getViewer().controls.enabled=false;pickButton.textContent='Cancel picking';status.textContent='Hover over the model to highlight a part. Click to select it. Escape cancels.';};
    window.addEventListener('pointermove',event=>{if(!picking||event.target.closest?.('#expression-modal .modal-card'))return;if(performance.now()-lastHover<45)return;lastHover=performance.now();const id=controller.pick(event.clientX,event.clientY);controller.setHover(id);status.textContent=id?'Highlighted: '+controller.entry(id).name:'Hover over hair, clothing or another model part.';},true);
    window.addEventListener('pointerdown',event=>{if(!picking||event.target.closest?.('#expression-modal .modal-card'))return;event.preventDefault();event.stopImmediatePropagation();const id=controller.pick(event.clientX,event.clientY);if(!id)return;part.value=id;updateColor();const name=controller.entry(id).name;stopPicking();status.textContent='Selected: '+name;},true);
    window.addEventListener('keydown',event=>{if(picking&&event.code==='Escape'){event.preventDefault();stopPicking();}},true);
    const close=document.getElementById('close-expression-modal'),closeOriginal=close.onclick;close.onclick=()=>{stopPicking();bones.stop();faceMapping.stop();closeOriginal?.();};
    tab(activeTab);return {refresh,stopMicrophone:mouth.stop};
}
