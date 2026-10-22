// Only authored, explicitly named visibility morphs; never guesses atlas regions.
export const visibilityParts = [
    {morph:'Hide_Wings',label:'Wings',materials:['Irida_Wings']},
    {morph:'Hide_Horns',label:'Horns',materials:['Irida_Horns']},
    {morph:'Hide_Top',label:'Top clothing',materials:['Irida_Top']},
];
export function loadVisibility(viewer,url) {
    viewer.partVisibility = new Map();
    viewer.partVisibilityMaterials = new Map();
    viewer.partVisibilityKey='sakura_model_visibility:'+url;
    let saved={};try{saved=JSON.parse(localStorage.getItem(viewer.partVisibilityKey)||'{}');}catch{}
    const names=new Set(viewer.getMorphNames?.()||[]);
    for(const part of visibilityParts)if(names.has(part.morph)) {
        viewer.partVisibility.set(part.morph,saved?.[part.morph]===true?1:0);
        const targets=[];
        viewer.model?.traverse?.(node=>{
            for(const material of Array.isArray(node.material)?node.material:node.material?[node.material]:[])
                if(part.materials.includes(material.name))targets.push({material,visible:material.visible!==false});
        });
        viewer.partVisibilityMaterials.set(part.morph,targets);
    }
    applyVisibility(viewer);
}
export function applyVisibility(viewer) {
    if(viewer.live2d)return;
    for(const [morph,weight]of viewer.partVisibility||[]) {
        viewer.setMorph(morph,weight);
        // Three's PMX path indexes material morphs but doesn't apply their
        // opacity operation. Dedicated exported materials make this explicit,
        // work with physics off, and preserve the original alpha/render state.
        for(const target of viewer.partVisibilityMaterials?.get(morph)||[])target.material.visible=weight<.5&&target.visible;
    }
}
export function setPartVisible(viewer,morph,visible) {
    if(!viewer.partVisibility?.has(morph))return false;
    viewer.partVisibility.set(morph,visible?0:1);
    applyVisibility(viewer);
    try{localStorage.setItem(viewer.partVisibilityKey,JSON.stringify(Object.fromEntries([...viewer.partVisibility].map(([key,value])=>[key,value===1]))));}catch{}
    return true;
}
export function refreshVisibilityControls(viewer,container) {
    if(!container)return;
    container.replaceChildren();
    for(const part of visibilityParts) {
        if(!viewer?.partVisibility?.has(part.morph))continue;
        const label=document.createElement('label');label.className='toggle-label';
        const input=document.createElement('input');input.type='checkbox';input.checked=viewer.partVisibility.get(part.morph)!==1;
        input.onchange=()=>setPartVisible(viewer,part.morph,input.checked);
        label.append(input,document.createTextNode(' Show '+part.label));container.append(label);
    }
    if(!container.childElementCount)container.textContent='This model has no authored wings, horns or top-clothing visibility controls.';
}
