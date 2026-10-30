// Snapshots are local evidence, not a guess at the artist's intended texture.
export function inspectLoadedTextures(viewer) {
    const issues=[],seen=new Set();let checked=0;
    const inspect=(texture,label)=>{
        if(!texture||seen.has(texture))return;seen.add(texture);checked++;
        const image=texture.source?.data||texture.image||texture.baseTexture;
        const width=image?.naturalWidth||image?.width,height=image?.naturalHeight||image?.height;
        if(!width||!height||image?.valid===false)issues.push(`${label}: texture image is not ready or failed to load.`);
        else if(!texture.isCompressedTexture)texture.needsUpdate=true;
    };
    if(viewer.live2d){
        viewer.live2d.avatar.textures.forEach((texture,i)=>inspect(texture,`Texture atlas ${i+1}`));
    }else viewer.model?.traverse(mesh=>{
        for(const material of Array.isArray(mesh.material)?mesh.material:[mesh.material]){
            if(!material)continue;
            // MMD material maps are non-enumerable uniform accessors, so an
            // Object.entries-only check silently skips their actual textures.
            for(const slot of ['map','gradientMap','matcap','normalMap','alphaMap','emissiveMap']){
                const texture=material[slot];
                if(texture?.isTexture)inspect(texture,`${material.name||'Material'} / ${slot}`);
            }
            if(material.map?.userData?.sakuraPmxFallback==='diffuse')issues.push(`${material.name||'Material'}: showing a neutral fallback instead of its diffuse artwork.`);
            if(/^sphere/.test(material.matcap?.userData?.sakuraPmxFallback||''))issues.push(`${material.name||'Material'}: showing a neutral fallback instead of its shine/sphere map.`);
            if(material.gradientMap?.userData?.sakuraPmxFallback==='toon'&&material.userData?.sakuraPmxRepairs?.includes('toon'))issues.push(`${material.name||'Material'}: showing a neutral fallback instead of its toon map.`);
            for(const [slot,texture] of Object.entries(material))if(texture?.isTexture)inspect(texture,`${material.name||'Material'} / ${slot}`);
        }
    });
    return {checked,issues};
}

export async function checkPmxTextureReferences(key,slots,isCurrent,request=fetch) {
    const references=slots.filter(s=>(s.chosen||s.original)&&!(s.chosen||s.original).startsWith('Shared toon ')&&(s.chosen||s.original)!=='(none)')
        .map(s=>({material:s.material,slot:s.slot,reference:s.chosen||s.original}));
    const response=await request('/api/models/texture-diagnose',{method:'POST',headers:{'Content-Type':'application/json'},
        signal:AbortSignal.timeout(30000),body:JSON.stringify({model:key,slots:references})});
    const data=await response.json();if(!response.ok)throw Error(data.error||'Texture check failed.');
    let repaired=0;
    for(const slot of data.slots){
        if(!isCurrent())throw Error('Model changed. Run the texture check on the selected model.');
        if(slot.status!=='repairable')continue;
        const saved=await request('/api/models/texture-material',{method:'POST',headers:{'Content-Type':'application/json'},
            signal:AbortSignal.timeout(10000),body:JSON.stringify({model:key,material:slot.material,slot:slot.slot,texture:slot.resolved})});
        if(!saved.ok)throw Error('Could not save the repaired texture reference.');
        repaired++;
    }
    return {checked:data.slots.length,repaired,issues:data.slots.filter(s=>!['ok','repairable'].includes(s.status))
        .map(s=>`Material ${s.material+1} / ${s.slot} (${s.reference}): ${s.message}`)};
}

async function snapshot(viewer){
    const frame=viewer.captureTextureDiagnosticFrame?viewer.captureTextureDiagnosticFrame(960):viewer.captureSpoutFrame(640);if(!frame)throw Error('Wait for the model to finish loading before taking a snapshot.');
    let canvas=frame.canvas;
    if(!canvas){canvas=document.createElement('canvas');canvas.width=frame.width;canvas.height=frame.height;
        canvas.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(frame.pixels),frame.width,frame.height),0,0);}
    return new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(Error('Model snapshot failed.')),'image/png'));
}

function store(key,record){
    return new Promise((resolve,reject)=>{
        const open=indexedDB.open('sakura-texture-diagnostics',1);
        open.onupgradeneeded=()=>open.result.createObjectStore('models');
        open.onerror=()=>reject(Error('The texture report could not be saved locally.'));
        open.onsuccess=()=>{const db=open.result,tx=db.transaction('models','readwrite');tx.objectStore('models').put(record,key);
            tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>{db.close();reject(Error('The texture report could not be saved locally.'));};};
    });
}

export function installTextureDiagnostics(getViewer,getKey,reloadModel,matchAppearance){
    const button=document.getElementById('model-texture-snapshot-check'),status=document.getElementById('model-texture-check-status');
    const images=['model-texture-before-image','model-texture-after-image'].map(id=>document.getElementById(id));
    let busy=false,urls=[],displayKey=null;
    const clear=()=>{urls.forEach(URL.revokeObjectURL);urls=[];images.forEach(image=>{image.hidden=true;image.removeAttribute('src');});};
    const refresh=()=>{if(displayKey!==getKey()){clear();status.textContent='Check texture decoding and repair confirmed PMX paths. This preserves original artwork and your saved colour overrides.';displayKey=getKey();}};
    button.onclick=async()=>{
        if(busy)return;const viewer=getViewer(),key=getKey(),identity=viewer?.live2d||viewer?.model;
        if(!identity||viewer._displayLoading){status.textContent='Load a model and wait until it is ready.';return;}
        busy=true;button.disabled=true;displayKey=key;clear();
        let current=()=>getViewer()===viewer&&getKey()===key&&(viewer.live2d||viewer.model)===identity;
        const view=viewer.model&&viewer.camera?.clone?{
            camera:viewer.camera.clone(),target:viewer.controls?.target?.clone(),
            position:viewer.model.position.clone(),quaternion:viewer.model.quaternion.clone(),scale:viewer.model.scale.clone()
        }:null;
        const restoreView=()=>{
            if(!view||getViewer()!==viewer||getKey()!==key||!viewer.model)return;
            viewer.model.position.copy(view.position);viewer.model.quaternion.copy(view.quaternion);viewer.model.scale.copy(view.scale);
            viewer.model.updateMatrixWorld(true);
            if(view.target)viewer.controls.target.copy(view.target);
            viewer.camera.copy(view.camera);viewer.camera.updateProjectionMatrix();viewer.camera.updateMatrixWorld(true);
        };
        try{
            viewer.materialEditor?.setHover(null);
            status.textContent='Taking snapshot and checking texture images…';
            const before=await snapshot(viewer);if(!current())throw Error('Model changed during the snapshot.');
            let editorOpened=false,editorNote='';
            if(/\.pmx$/i.test(key)){
                const openEditor=window.pywebview?.api?.open_pmx_editor;
                if(openEditor&&!(matchAppearance&&window.pywebview?.api?.capture_pmx_appearance_reference)){
                    status.textContent='Opening this model in PMX Editor, then checking its texture references…';
                    try{
                        const opened=await window.pywebview.api.open_pmx_editor(key);
                        editorOpened=opened?.opened===true;
                        editorNote=editorOpened?' Launched PMX Editor with the selected file for comparison.':opened?.cancelled?' PMX Editor selection cancelled.':'';
                    }catch(error){editorNote=` PMX Editor could not open: ${error.message||error}.`;}
                }else editorNote=' PMX Editor opens from the Windows desktop app; this browser can still check the texture files.';
                if(!current())throw Error('Model changed while opening PMX Editor.');
            }
            const loaded=inspectLoadedTextures(viewer);
            const report=/\.pmx$/i.test(key)?await checkPmxTextureReferences(key,viewer.pmxTextureSlots||[],current):{checked:loaded.checked,repaired:0,issues:[]};
            report.editorOpened=editorOpened;report.editorNote=editorNote;
            if(!current())throw Error('Model changed during the texture check.');
            if(/\.pmx$/i.test(key)||report.repaired||loaded.issues.length){
                status.textContent=`Saved ${report.repaired} confirmed texture path repairs. Reloading textures with the format-aware decoder…`;
                // The files may have been restored while this model still owns
                // the earlier white fallback. Re-read bytes, not just file paths.
                viewer.textureReloadRevision=Math.max(Date.now(),(viewer.textureReloadRevision||0)+1);
                await reloadModel(key);
                if(getViewer()!==viewer||getKey()!==key||viewer._displayLoading)throw Error('Model changed or could not be reloaded. Repairs remain saved for its next load.');
                const reloadedIdentity=viewer.live2d||viewer.model;current=()=>getViewer()===viewer&&getKey()===key&&(viewer.live2d||viewer.model)===reloadedIdentity;
                restoreView();
            }
            if(/\.pmx$/i.test(key)&&matchAppearance&&window.pywebview?.api?.capture_pmx_appearance_reference){
                status.textContent='Texture paths checked. Matching rendered appearance with PMX Editor…';
                report.appearance=await matchAppearance();
                const unmatched=viewer.pmxReferenceAudit?.unmatched||[];
                if(unmatched.length)report.issues.push('Reference shading is unsupported for '+unmatched.length+' materials.');
                if(!current())throw Error('Model changed during appearance matching.');
                if(report.appearance?.matched)editorNote=' Read an actual PMX Editor reference and compared the whole model plus visible sampled materials.';
                else report.issues.push('Appearance matching did not finish: '+(report.appearance?.error||'No editor reference returned.'));
            }
            const after=await snapshot(viewer);if(!current())throw Error('Model changed during the texture check.');
            report.issues.push(...inspectLoadedTextures(viewer).issues);
            const summary=`Checked all ${report.checked} texture references/images across the whole model. ${report.repaired} path repairs saved.`;
            const record={before,after,report,time:Date.now()};await store(key,record);if(!current())return;
            for(const [i,blob]of [before,after].entries()){const url=URL.createObjectURL(blob);urls.push(url);images[i].src=url;images[i].hidden=false;}
            status.textContent=summary+(report.issues.length?' Needs attention: '+report.issues.join(' '):' No missing or unreadable textures detected.')+editorNote+' Snapshots and report saved locally for this model.';
        }catch(error){if(getKey()===key)status.textContent=error.message;}
        finally{if(current())restoreView();busy=false;button.disabled=false;}
    };
    return {refresh,stop:clear};
}
