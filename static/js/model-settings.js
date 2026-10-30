import {installPmxAppearance} from './pmx-render-controls.js?v=3';
import {ModelMaterials,storedRemap} from './model-materials.js?v=pmx-colour4';
import {installColorDial} from './color-dial.js?v=assistant69';
import {installMouthSettings} from './mouth-settings.js?v=audio-route5';
import {installLive2DFaceMapping} from './live2d-face-mapping.js?v=2';
import {installBoneSettings} from './model-bones.js?v=persistent5';
import {installTextureDiagnostics} from './texture-diagnostics.js?v=reference-generic8';
import {tintEdit,opacityEdit} from './part-appearance.js?v=1';
import {installMaterialExpressions} from './material-expressions.js?v=1';

export function installModelSettings(getViewer,getModelKey,refreshPmx,getMic,reloadModel) {
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
    const textureDiagnostics=installTextureDiagnostics(getViewer,getModelKey,reloadModel,()=>appearance.match());
    const appearance=installPmxAppearance(getViewer,getModelKey);
    const lighting=document.getElementById('model-lighting-controls');
    for(const id of ['character-glow-slider','light-angle-slider','light-elevation-slider','gloss-boost-slider']){
        const group=document.getElementById(id)?.closest('.slider-group');if(group)lighting.append(group);
    }
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
    const editMode=document.createElement('select');editMode.id='model-part-edit-mode';editMode.setAttribute('aria-label','Choose what to change on the selected part');
    editMode.add(new Option('Change color','color'));editMode.add(new Option('Change transparency','transparency'));
    const modeLabel=document.createElement('label');modeLabel.className='companion-part-edit-mode';modeLabel.htmlFor=editMode.id;modeLabel.append(document.createTextNode('What would you like to change?'),editMode);
    document.getElementById('model-pick-part').before(modeLabel);
    const separatePartEdits=()=>document.body.classList.contains('companion-ui-active')||document.body.classList.contains('tracking-only');
    const transparencyMode=()=>separatePartEdits()&&editMode.value==='transparency';
    const syncEditMode=()=>{
        panel.classList.toggle('model-edit-transparency',transparencyMode());
        document.getElementById('model-color-apply').textContent=transparencyMode()?'Apply transparency':'Apply color';
        document.getElementById('model-color-reset').textContent=transparencyMode()?'Restore original transparency':'Restore original color';
    };
    editMode.onchange=()=>{syncEditMode();updateColor();};
    new MutationObserver(syncEditMode).observe(document.body,{attributes:true,attributeFilter:['class']});
    const tab=name=>{
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
        textureDiagnostics.refresh();
        void appearance.refresh();
        const viewer=getViewer(),identity=viewer?.live2d||viewer?.model,key=getModelKey();
        faceMapping.refresh();
        document.querySelector('[data-model-tab="mouth"]').hidden=false;
        if(!identity){status.textContent='Load a model to customize its appearance.';return;}
        if(root!==identity||key!==modelKey){
            stopPicking();
            lightingTargetId=null;
            viewer?.setCharacterLightingTarget(null);
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
        fill(part,controller.colorTargets());fill(texture,controller.remapTargets());updateColor();materialExpressions.refresh();
        updateLightingTarget();
        document.getElementById('model-color-hint').textContent=viewer.live2d
            ? 'Choose a Live2D ArtMesh to tint. Names come from the imported rig. Tint preserves its masks and transparency.'
            : 'Choose a material for hair, clothing or another part. Coloring preserves texture detail and transparency.';
        document.getElementById('model-remap-hint').textContent=viewer.live2d
            ? 'Replace a texture atlas with an image using the same UV layout. One atlas can contain several body parts.'
            : 'Replace the diffuse image for a material. Use a texture designed for this model’s UV layout.';
        document.getElementById('model-expression-hint').textContent=viewer.areAiExpressionsAutomatic?.()
            ? 'Reactions on: AI selects expressions. Turn Reactions off to choose expressions manually.'
            : 'Preview imported expressions and assign their hotkeys.';
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
    document.getElementById('model-color-apply').onclick=()=>action(async current=>{
        current.setHover(null);
        const existing=current.colors[part.value];
        const settings=separatePartEdits()
            ?transparencyMode()?opacityEdit(existing,1-Number(opacity.value)/100):tintEdit(existing,picker.value,Number(strength.value)/100)
            :{color:picker.value,strength:Number(strength.value)/100,opacity:1-Number(opacity.value)/100};
        current.setColor(part.value,settings);saveColors();
    });
    document.getElementById('model-color-reset').onclick=()=>action(async current=>{
        const existing=current.colors[part.value];
        const settings=separatePartEdits()
            ?transparencyMode()?opacityEdit(existing,1):tintEdit(existing,'#ffffff',0):null;
        current.setColor(part.value,settings);saveColors();updateColor();
    });
    document.getElementById('model-remap-apply').onclick=()=>action(async current=>{
        const blob=file.files[0];if(!blob)throw Error('Choose a PNG, JPG, WebP, BMP or TGA replacement image first.');
        const id=texture.value,key=modelKey;await current.setRemap(id,blob);await storedRemap(key,id,blob);file.value='';
    });
    document.getElementById('model-remap-reset').onclick=()=>action(async current=>{const id=texture.value;await current.setRemap(id,null);await storedRemap(modelKey,id,null);});
    let picking=false,lastHover=0,pickMode='color',lightingTargetId=null;
    const pickButton=document.getElementById('model-pick-part');
    const lightingPick=document.getElementById('model-lighting-pick'),lightingWhole=document.getElementById('model-lighting-whole');
    const lightingStatus=document.getElementById('model-lighting-target-status');
    const updateLightingTarget=()=>{const entry=controller?.entry(lightingTargetId);lightingStatus.textContent=entry?'Target: '+entry.name+'. Gloss and bloom apply only to this material.':'Target: full model. Gloss and bloom apply across the model.';};
    const stopPicking=()=>{picking=false;document.body.classList.remove('model-part-picking');controller?.setHover(null);const viewer=getViewer();if(viewer?.controls)viewer.controls.enabled=true;pickButton.textContent='Pick part on model';lightingPick.textContent='Pick part for gloss and bloom';};
    const startPicking=mode=>{if(picking){stopPicking();return;}if(!controller)return;pickMode=mode;tab('coloring');picking=true;document.body.classList.add('model-part-picking');getViewer().controls.enabled=false;if(mode==='lighting')lightingPick.textContent='Cancel picking';else pickButton.textContent='Cancel picking';status.textContent='Hover over the model to highlight a part. Click to select it. Escape cancels.';};
    pickButton.onclick=()=>startPicking('color');
    lightingPick.onclick=()=>startPicking('lighting');
    lightingWhole.onclick=()=>{lightingTargetId=null;getViewer()?.setCharacterLightingTarget(null);updateLightingTarget();status.textContent='Gloss and bloom now affect the full model.';};
    window.addEventListener('pointermove',event=>{if(!picking||event.target.closest?.('#expression-modal .modal-card'))return;if(performance.now()-lastHover<45)return;lastHover=performance.now();const id=controller.pick(event.clientX,event.clientY);controller.setHover(id);status.textContent=id?'Highlighted: '+controller.entry(id).name:'Hover over hair, clothing or another model part.';},true);
    window.addEventListener('pointerdown',event=>{if(!picking||event.target.closest?.('#expression-modal .modal-card'))return;event.preventDefault();event.stopImmediatePropagation();const id=controller.pick(event.clientX,event.clientY);if(!id)return;const entry=controller.entry(id);part.value=id;updateColor();const name=entry.name;if(pickMode==='lighting'){if(!entry.material){status.textContent='Gloss and bloom targeting is available for 3D model materials.';return;}lightingTargetId=id;getViewer()?.setCharacterLightingTarget(entry.material);updateLightingTarget();}stopPicking();status.textContent='Selected: '+name;},true);
    window.addEventListener('keydown',event=>{if(picking&&event.code==='Escape'){event.preventDefault();stopPicking();}},true);
    const close=document.getElementById('close-expression-modal'),closeOriginal=close.onclick;close.onclick=()=>{stopPicking();bones.stop();textureDiagnostics.stop();faceMapping.stop();closeOriginal?.();};
    const materialExpressions=installMaterialExpressions({controller:()=>controller,key:()=>modelKey,part:()=>part.value,
        edit:()=>transparencyMode()?{channel:'opacity',value:1-Number(opacity.value)/100}:{channel:'color',value:{color:picker.value,strength:Number(strength.value)/100}},
        save:saveColors,changed:updateColor});
    tab(activeTab);return {refresh,stopMicrophone:mouth.stop};
}
