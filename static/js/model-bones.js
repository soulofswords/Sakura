import * as THREE from 'three';

export class ModelBones {
    constructor(viewer,key){
        this.viewer=viewer;this.key=key;this.entries=[];this.disabled=new Set();
        const seen=new Set(),physics=new Map((viewer.physics?.nodes||[]).map(n=>[n.bone,n]));
        viewer.model?.traverse(bone=>{if(!bone.isBone||seen.has(bone))return;seen.add(bone);
            const node=physics.get(bone);
            this.entries.push({id:String(this.entries.length),name:bone.name||'Unnamed bone',bone,
                position:(node?.restLocal||bone.position).clone(),quaternion:(node?.restQuat||bone.quaternion).clone(),scale:bone.scale.clone()});
        });
        try{const saved=JSON.parse(localStorage.getItem('sakura_disabled_bones:'+key)||'[]');for(const entry of this.entries)if(saved.includes(entry.id+'|'+entry.name))this.disabled.add(entry.id);}catch(_){}
        this.sync();
    }
    sync(){if(this.viewer.physics)this.viewer.physics.disabledBones=new Set(this.entries.filter(e=>this.disabled.has(e.id)).map(e=>e.bone));this.viewer._syncVrmPhysics?.();}
    toggle(id,disabled){if(disabled)this.disabled.add(id);else{this.disabled.delete(id);const entry=this.entries.find(e=>e.id===id);if(entry)this.viewer.rigMonitor?.unfreezeBone(entry.bone);}this.sync();this.viewer.physics?.reset();this.save();this.apply();}
    save(){localStorage.setItem('sakura_disabled_bones:'+this.key,JSON.stringify(this.entries.filter(e=>this.disabled.has(e.id)).map(e=>e.id+'|'+e.name)));}
    apply(){for(const entry of this.entries)if(this.disabled.has(entry.id)){entry.bone.position.copy(entry.position);entry.bone.quaternion.copy(entry.quaternion);entry.bone.scale.copy(entry.scale);entry.bone.updateMatrix();}if(this.disabled.size)this.viewer.model?.updateMatrixWorld(true);}
    pick(x,y){
        const rect=this.viewer.renderer.domElement.getBoundingClientRect(),point=new THREE.Vector3();let selected=null,distance=24;
        this.viewer.model?.updateMatrixWorld(true);
        for(const entry of this.entries){entry.bone.getWorldPosition(point).project(this.viewer.camera);if(point.z<-1||point.z>1)continue;
            const d=Math.hypot(rect.left+(point.x+1)*rect.width/2-x,rect.top+(1-point.y)*rect.height/2-y);
            if(d<distance){distance=d;selected=entry.id;}}
        return selected;
    }
}

export function installBoneSettings(getViewer,getKey){
    const select=document.getElementById('model-bone-select'),disabled=document.getElementById('model-bone-disabled'),status=document.getElementById('model-bone-status'),search=document.getElementById('model-bone-search');
    let controller,identity,key,picking=false,helper;
    const stop=()=>{picking=false;if(helper){getViewer()?.scene.remove(helper);helper.geometry.dispose();helper.material.dispose();helper=null;}document.body.classList.remove('picking-model-part');};
    const update=()=>{const entry=controller?.entries.find(e=>e.id===select.value);disabled.checked=!!controller?.disabled.has(select.value)||!!getViewer()?.diagnosticFrozenBones?.has(entry?.bone);disabled.disabled=!controller?.entries.length;status.textContent=controller?.entries.length?`${controller.disabled.size} manually frozen / ${controller.entries.length} bones. Frozen bones keep their local rest pose; other bones still move.`:'Bone controls are available for PMX and VRM models. Live2D uses authored parameters.';
        const viewer=getViewer(),names=controller?.entries.filter(e=>viewer?.diagnosticFrozenBones?.has(e.bone)).map(e=>e.name)||[];
        document.getElementById('model-bone-auto-status').textContent=(viewer?.rigAnalysis?.status||'No automatic bone check available for this model.')+(names.length?' Auto-frozen: '+names.join(', '):'');};
    const fill=()=>{const selected=select.value;select.replaceChildren();for(const entry of controller?.entries||[])if(entry.name.toLowerCase().includes(search.value.toLowerCase()))select.add(new Option(entry.name,entry.id));if([...select.options].some(o=>o.value===selected))select.value=selected;update();};
    const refresh=()=>{const viewer=getViewer(),model=viewer?.model,newKey=getKey();if(identity!==model||key!==newKey){stop();clearImages();for(const id of ['model-bone-reference-image','model-bone-diagnostic-image']){const image=document.getElementById(id);image.hidden=true;image.removeAttribute('src');}identity=model;key=newKey;controller=model&&!viewer.live2d?new ModelBones(viewer,key):null;if(viewer)viewer.boneControls=controller;}fill();};
    select.onchange=update;search.oninput=fill;disabled.onchange=()=>{controller?.toggle(select.value,disabled.checked);update();};
    document.getElementById('model-bone-reset').onclick=()=>{if(controller){controller.disabled.clear();controller.sync();controller.save();controller.viewer.physics?.reset();}update();};
    document.getElementById('model-bone-auto-reset').onclick=()=>{getViewer()?.rigMonitor?.reset();update();};
    document.getElementById('model-bone-snapshot-check').onclick=()=>{if(!getViewer()?.rigMonitor?.checkNow())document.getElementById('model-bone-auto-status').textContent='Load a PMX or VRM model with physics bones to run this check.';};
    let imageUrls=[];
    const clearImages=()=>{for(const url of imageUrls)URL.revokeObjectURL(url);imageUrls=[];};
    document.getElementById('model-bone-auto-images').onclick=()=>{
        clearImages();const viewer=getViewer();let shown=false;
        for(const [id,blob]of [['model-bone-reference-image',viewer?.rigDiagnosticReference],['model-bone-diagnostic-image',viewer?.rigDiagnosticImage]]){
            const image=document.getElementById(id);image.hidden=!blob;if(blob){const url=URL.createObjectURL(blob);imageUrls.push(url);image.src=url;shown=true;}else image.removeAttribute('src');
        }
        if(!shown)document.getElementById('model-bone-auto-status').textContent='Keep the model loaded for eight seconds to capture the diagnostic images.';
    };
    window.addEventListener('sakura-rig-analysis',update);
    document.getElementById('model-bone-pick').onclick=()=>{if(!controller)return;stop();picking=true;helper=new THREE.SkeletonHelper(identity);helper.material.depthTest=false;helper.material.transparent=true;helper.renderOrder=1000;getViewer().scene.add(helper);document.body.classList.add('picking-model-part');status.textContent='Click a visible bone joint, or use the searchable list. Escape cancels.';};
    window.addEventListener('pointerdown',event=>{if(!picking||event.target.closest?.('#expression-modal .modal-card'))return;event.preventDefault();event.stopImmediatePropagation();const id=controller.pick(event.clientX,event.clientY);if(id===null)return;search.value='';fill();select.value=id;stop();update();},true);
    window.addEventListener('keydown',e=>{if(picking&&e.key==='Escape')stop();});
    return{refresh,stop:()=>{stop();clearImages();}};
}
