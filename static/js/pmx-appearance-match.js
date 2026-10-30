import {applyPmxAppearance,normalizePmxAppearance,PMX_RENDER_CONTROLS} from './pmx-render-controls.js?v=3';

// View-independent colour matching. This is not a UV/texture reconstruction
// and cannot reproduce unsupported editor effects or unseen geometry.
export function appearanceStats(frame) {
    const hist=Array.from({length:3},()=>new Uint32Array(256));let count=0;
    for(let i=0;i<frame.pixels.length;i+=4){
        const d=frame.pixels,alpha=d[i+3]/255;
        // Render-target readback has already blended RGB against clear black.
        // Native black-backed RGB is comparable directly; multiplying by
        // alpha here would darken translucent surfaces a second time.
        const rgb=[d[i],d[i+1],d[i+2]];
        if(!alpha||Math.max(...rgb)<8)continue;
        count++;for(let c=0;c<3;c++)hist[c][rgb[c]]++;
    }
    if(count<40)throw Error('The reference does not contain enough visible model pixels.');
    const levels=[.1,.25,.5,.75,.9],values=[];
    for(const bins of hist){let sum=0;for(let i=0;i<256;i++)sum+=i*bins[i];values.push(sum/count/255);
        for(const level of levels){let n=0,index=0;while(index<255&&(n+=bins[index])<count*level)index++;values.push(index/255);}
    }
    return values;
}
export function appearanceLoss(a,b){return a.reduce((sum,value,i)=>sum+(value-b[i])**2,0)/a.length;}
export async function referenceFrame(url) {
    if(typeof url!=='string'||!url.startsWith('data:image/png;base64,')||url.length>24000000)throw Error('PMX Editor returned an invalid reference image.');
    const image=new Image();await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(Error('Could not decode the editor reference.'));image.src=url;});
    if(image.width*image.height>16000000)throw Error('The editor reference image is too large.');
    const canvas=document.createElement('canvas'),scale=Math.min(1,512/Math.max(image.width,image.height));canvas.width=Math.max(1,Math.round(image.width*scale));canvas.height=Math.max(1,Math.round(image.height*scale));
    const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0,canvas.width,canvas.height);
    return {width:canvas.width,height:canvas.height,pixels:ctx.getImageData(0,0,canvas.width,canvas.height).data};
}
export async function fitPmxAppearance(viewer,reference,initial,{current=()=>true,progress=()=>{},parts=[]}={}) {
    const root=viewer.model,start=normalizePmxAppearance(initial),target=appearanceStats(reference);
    let best={...start},bestLoss=Infinity,evaluations=0,lastParts=[],baselineParts=[];
    const paired=[];
    for(const part of parts){
        const material=root.material?.[part.material];if(!material||material.visible===false)continue;
        try{paired.push({material,target:appearanceStats(part.frame)});}catch{/* Hidden material has no measurable pixels in this view. */}
    }
    const materials=[];root.traverse(object=>{for(const material of Array.isArray(object.material)?object.material:[object.material])if(material&&!materials.includes(material))materials.push(material);});
    const visible=materials.map(material=>material.visible);
    // Freeze the measurable pairs at baseline. Hidden outfits and occluded
    // parts are ordinary; they must not invalidate otherwise usable references.
    function partLoss(part){
        try{return appearanceLoss(appearanceStats(viewer.captureTextureDiagnosticFrame(192)),part.target);}
        catch(error){if(/enough visible/.test(error.message))return null;throw error;}
    }
    try{
        for(let i=paired.length-1;i>=0;i--){
            materials.forEach((material,j)=>material.visible=visible[j]&&material===paired[i].material);
            if(partLoss(paired[i])===null)paired.splice(i,1);
        }
    }finally{materials.forEach((material,i)=>material.visible=visible[i]);}
    function evaluate(settings){
        if(!current()||viewer.model!==root)throw Error('Model changed while matching appearance.');
        applyPmxAppearance(root,settings);evaluations++;
        // Every evaluation measures the composite too, so unselected materials
        // remain constrained, including models with no opaque material parts.
        const whole=appearanceLoss(appearanceStats(viewer.captureTextureDiagnosticFrame(192)),target);
        lastParts=[whole];
        try{for(const part of paired){
            materials.forEach((material,i)=>material.visible=visible[i]&&material===part.material);
            lastParts.push(partLoss(part)??Infinity);
        }}finally{materials.forEach((material,i)=>material.visible=visible[i]);}
        return lastParts.reduce((sum,value)=>sum+value,0)/lastParts.length;
    }
    try {
        const before=evaluate(start);if(!Number.isFinite(before))throw Error('A reference material is not visible in Sakura. Repair textures or choose another viewing angle before matching.');bestLoss=before;baselineParts=[...lastParts];
        // Bounded coordinate descent. Directional shading is preserved to avoid
        // fitting a pose-dependent shadow into a permanent model colour.
        for(const step of [.3,.12,.05])for(const [key,label,min,max]of PMX_RENDER_CONTROLS){
            if(key==='normal')continue;
            let candidateBest=best,candidateLoss=bestLoss;
            for(const sign of [-1,1]){
                const value=Math.max(min,Math.min(max,best[key]+sign*step));if(value===best[key])continue;
                const candidate={...best,[key]:value},loss=evaluate(candidate);
                if(loss<candidateLoss&&lastParts.every((value,i)=>value<=(baselineParts[i]??0)+.0001)){candidateBest=candidate;candidateLoss=loss;}
            }
            best=candidateBest;bestLoss=candidateLoss;
            progress({evaluations,before,after:bestLoss});
            await new Promise(resolve=>requestAnimationFrame(resolve));
        }
        if(!current()||viewer.model!==root)throw Error('Model changed while matching appearance.');
        const improved=bestLoss<before*.995&&before-bestLoss>.00001;
        const settings=improved?best:start;applyPmxAppearance(root,settings);
        return {settings,before,after:improved?bestLoss:before,improved,evaluations,metric:paired.length?'whole-frame and corresponding-material RGB means and quantiles':'whole-frame RGB means and quantiles',materials:paired.length,skippedMaterials:parts.length-paired.length};
    }catch(error){if(viewer.model===root)applyPmxAppearance(root,start);throw error;}
}
