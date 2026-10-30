// Per-model presentation overrides. Defaults leave the authored PMX path intact.
export const PMX_RENDER_CONTROLS = [
    ['brightness','Brightness',0,2,1],
    ['ambient','Ambient fill',0,2,1],
    ['diffuse','Authored material tint',0,1,1],
    ['toon','Toon shading',0,1,1],
    ['normal','Directional shading',0,1,0],
    ['sphere','Sphere / shine maps',0,2,1],
    ['specular','Specular highlights',0,2,1],
    ['saturation','Colour saturation',0,2,1],
];
export function normalizePmxAppearance(value={}) {
    return Object.fromEntries(PMX_RENDER_CONTROLS.map(([key,label,min,max,fallback])=>{
        const number=typeof value?.[key]==='number'?value[key]:NaN;
        return [key,Number.isFinite(number)?Math.max(min,Math.min(max,number)):fallback];
    }));
}
export function pmxAppearanceKey(key) {
    const path=String(key||'').split(/[?#]/)[0].replace(/^.*?\/models\//,'').replace(/\\/g,'/');
    try{return decodeURIComponent(path);}catch{return path;}
}
export function readPmxAppearance(key) {
    try{return normalizePmxAppearance(JSON.parse(localStorage.getItem('sakura_pmx_appearance:'+pmxAppearanceKey(key))||'{}'));}
    catch{return normalizePmxAppearance();}
}
export function applyPmxAppearance(root,settings) {
    const values=normalizePmxAppearance(settings);
    root?.traverse(object=>{for(const material of Array.isArray(object.material)?object.material:[object.material]){
        if(!material?.userData?.sakuraPmxReference)continue;
        for(const [key,value] of Object.entries(values)){
            const uniform=material.uniforms?.['sakuraPmxControl_'+key];if(uniform)uniform.value=value;
        }
    }});
    return values;
}
function snapshotStore(key,record) {
    return new Promise((resolve,reject)=>{
        const request=indexedDB.open('sakura-pmx-appearance',1);
        request.onupgradeneeded=()=>request.result.createObjectStore('snapshots');
        request.onerror=()=>reject(Error('Appearance snapshot storage is unavailable.'));
        request.onsuccess=()=>{const db=request.result,tx=db.transaction('snapshots',record?'readwrite':'readonly'),store=tx.objectStore('snapshots');
            const op=record?store.put(record,key):store.get(key);let result;
            op.onsuccess=()=>result=op.result;
            tx.oncomplete=()=>{db.close();resolve(result);};tx.onabort=tx.onerror=()=>{db.close();reject(Error('Could not save the appearance snapshot.'));};
        };
    });
}
export function installPmxAppearance(getViewer,getKey) {
    const host=document.getElementById('model-lighting-controls');
    if(!host)return {refresh(){}};
    const section=document.createElement('section');section.id='pmx-appearance-controls';
    const title=document.createElement('h4');title.textContent='PMX appearance';section.append(title);
    const hint=document.createElement('p');hint.className='modal-hint';hint.textContent='Saved for this model. Automatic matching captures PMX Editor and adjusts these sliders only when the measured colour match improves. It cannot replace missing textures or copy unsupported effects.';section.append(hint);
    const inputs=new Map();
    const status=document.createElement('p');status.className='modal-hint';status.setAttribute('role','status');
    let currentKey='',revision=0,imageUrl=null;
    for(const [key,label,min,max]of PMX_RENDER_CONTROLS){
        const group=document.createElement('div');group.className='slider-group';
        const text=document.createElement('label'),value=document.createElement('span'),input=document.createElement('input');
        input.type='range';input.id='pmx-appearance-'+key;input.min=min*100;input.max=max*100;input.step='1';text.htmlFor=input.id;text.append(label+': ',value);group.append(text,input);section.append(group);inputs.set(key,{input,value});
        input.oninput=()=>{
            if(pmxAppearanceKey(getKey())!==currentKey)return;
            const values=Object.fromEntries([...inputs].map(([name,row])=>[name,Number(row.input.value)/100]));
            try{localStorage.setItem('sakura_pmx_appearance:'+currentKey,JSON.stringify(values));applyPmxAppearance(getViewer()?.model,values);value.textContent=input.value+'%';status.textContent='Saved for this model. Take another appearance snapshot to compare.';}
            catch(error){status.textContent=error.message;}
        };
    }
    const reset=document.createElement('button');reset.id='pmx-appearance-reset';reset.type='button';reset.textContent='Reset appearance sliders';
    const snapshot=document.createElement('button');snapshot.id='pmx-appearance-snapshot';snapshot.type='button';snapshot.textContent='Match appearance from PMX Editor';
    const image=document.createElement('img');image.alt='Saved full-model appearance snapshot';image.hidden=true;image.style.cssText='max-width:100%;max-height:340px;object-fit:contain';
    const referenceImage=document.createElement('img');referenceImage.alt='Actual PMX Editor reference';referenceImage.hidden=true;referenceImage.style.cssText=image.style.cssText;
    const show=record=>{referenceImage.hidden=!record?.reference;if(record?.reference?.startsWith('data:image/png;base64,'))referenceImage.src=record.reference;else referenceImage.removeAttribute('src');if(imageUrl)URL.revokeObjectURL(imageUrl);imageUrl=null;image.hidden=!record?.image;if(record?.image){imageUrl=URL.createObjectURL(record.image);image.src=imageUrl;}else image.removeAttribute('src');};
    async function refresh(){
        const generation=++revision;currentKey=pmxAppearanceKey(getKey());
        section.hidden=!/\.pmx$/i.test(currentKey)||!getViewer()?.model;
        if(section.hidden){show(null);return;}
        const values=readPmxAppearance(currentKey);applyPmxAppearance(getViewer().model,values);
        for(const [key,row]of inputs){row.input.value=Math.round(values[key]*100);row.value.textContent=row.input.value+'%';}
        show(null);status.textContent='Appearance sliders are independent of texture repairs.';
        try{const record=await snapshotStore(currentKey);if(generation===revision){show(record);undo.hidden=!record?.match?.improved;}}catch(error){if(generation===revision)status.textContent=error.message;}
    }
    reset.onclick=()=>{try{localStorage.removeItem('sakura_pmx_appearance:'+currentKey);void refresh();}catch(error){status.textContent=error.message;}};
    let matching=false;
    snapshot.onclick=async()=>{
        const key=currentKey,viewer=getViewer(),model=viewer?.model,generation=revision;
        if(!model||pmxAppearanceKey(getKey())!==key)return;
        if(matching)return;
        matching=true;snapshot.disabled=true;reset.disabled=true;for(const row of inputs.values())row.input.disabled=true;
        const initial=readPmxAppearance(key);let accepted=false;
        const current=()=>generation===revision&&viewer.model===model&&pmxAppearanceKey(getKey())===key;
        try{
            const native=window.pywebview?.api?.capture_pmx_appearance_reference;
            if(!native)throw Error('Automatic appearance matching requires the Windows desktop app and PMX Editor.');
            viewer.materialEditor?.setHover(null);
            status.textContent='Opening an owned PMX Editor to capture its actual rendered appearance…';
            const direction=viewer.camera.position.clone().sub(viewer.controls.target).applyQuaternion(model.quaternion.clone().invert()).normalize().toArray();
            const result=await native(key,direction);
            if(!current())throw Error('Model changed while reading PMX Editor.');
            if(result?.model!==key)throw Error('Editor reference does not match the selected model.');
            const {referenceFrame,fitPmxAppearance}=await import('./pmx-appearance-match.js?v=3');
            const reference=await referenceFrame(result.image);
            if(!Array.isArray(result.parts)||result.parts.length>6)throw Error('PMX Editor did not return material references. No appearance changes were saved.');
            const parts=[];for(const part of result.parts){if(!Number.isInteger(part.material)||part.material<0||part.material>=model.material.length)throw Error('Invalid editor material reference.');parts.push({material:part.material,frame:await referenceFrame(part.image)});}
            const match=await fitPmxAppearance(viewer,reference,initial,{current,parts,progress:row=>{
                status.textContent='Matching against the PMX Editor reference… '+row.evaluations+' comparisons';
            }});
            if(!current())throw Error('Model changed during appearance matching.');
            const frame=viewer.captureTextureDiagnosticFrame(960);
            const canvas=document.createElement('canvas');canvas.width=frame.width;canvas.height=frame.height;
            canvas.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(frame.pixels),frame.width,frame.height),0,0);
            const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!blob)throw Error('Appearance snapshot failed.');
            if(!current())throw Error('Model changed during the snapshot.');
            const record={image:blob,reference:result.image,settings:match.settings,previous:initial,model:key,createdAt:new Date().toISOString(),match,lighting:result.lighting};
            await snapshotStore(key,record);
            if(!current())throw Error('Model changed while saving appearance.');
            localStorage.setItem('sakura_pmx_appearance:'+key,JSON.stringify(match.settings));accepted=true;
            for(const [name,row]of inputs){row.input.value=Math.round(match.settings[name]*100);row.value.textContent=row.input.value+'%';}
            show(record);undo.hidden=!match.improved;
            status.textContent=match.improved?'Adjusted colour balance toward the editor reference and saved appearance. Measured colour difference reduced by '+Math.round((1-match.after/match.before)*100)+'%.':'Editor reference captured; current sliders already gave the closest measured colour match. No slider values changed.';
            if(match.skippedMaterials)status.textContent+=' Skipped '+match.skippedMaterials+' hidden or unmeasurable material references; the whole model was still compared.';
            const unmatched=viewer.pmxReferenceAudit?.unmatched||[];
            if(unmatched.length)status.textContent+=' Reference shading is unsupported for '+unmatched.length+' materials.';
            status.textContent+=' Texture files are unchanged. Pose, physics and unsupported effects may still differ.';
            return {matched:true,improved:match.improved,before:match.before,after:match.after};
        }catch(error){if(current())status.textContent=error.message;return {matched:false,error:error.message};}
        finally{
            if(!accepted&&viewer.model===model)applyPmxAppearance(model,initial);
            matching=false;snapshot.disabled=false;reset.disabled=false;for(const row of inputs.values())row.input.disabled=false;
        }
    };
    const undo=document.createElement('button');undo.type='button';undo.id='pmx-appearance-undo';undo.textContent='Undo automatic appearance match';undo.hidden=true;
    undo.onclick=async()=>{
        const key=currentKey,model=getViewer()?.model,generation=revision;
        try{const record=await snapshotStore(key);if(generation!==revision||getViewer()?.model!==model||!record?.previous)return;
            localStorage.setItem('sakura_pmx_appearance:'+key,JSON.stringify(record.previous));await refresh();undo.hidden=true;status.textContent='Restored appearance from before automatic matching.';
        }catch(error){if(generation===revision)status.textContent=error.message;}
    };
    section.append(reset,snapshot,undo,status,referenceImage,image);host.append(section);
    return {refresh,match:()=>snapshot.onclick()};
}
