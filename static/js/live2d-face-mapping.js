export const FACE_SIGNALS=['cheekPuff','jawOpen','mouthPucker','mouthFunnel','mouthSmileLeft','mouthSmileRight','mouthFrownLeft','mouthFrownRight','mouthLeft','mouthRight','jawLeft','jawRight','mouthClose'];
const matches={cheekPuff:/cheek.*puff|puff|鼓腮|嘟腮|ふくれ|ぷく|頬膨/i,jawOpen:/mouthopen|jawopen/i,mouthPucker:/pucker|嘟嘴|すぼめ/i,mouthFunnel:/funnel/i,mouthSmileLeft:/smile.*left|smilel$/i,mouthSmileRight:/smile.*right|smiler$/i,mouthFrownLeft:/frown.*left|frownl$/i,mouthFrownRight:/frown.*right|frownr$/i,mouthLeft:/mouthleft|mouthl$/i,mouthRight:/mouthright|mouthr$/i,jawLeft:/jawleft/i,jawRight:/jawright/i,mouthClose:/mouthclose/i};
export function faceMappingTargets(live){
    const ids=Array.from(live?.avatar?.internalModel?.coreModel?._model?.parameters?.ids||[]);
    return [...ids.map(id=>({id,label:live.parameterLabels?.[id]?live.parameterLabels[id]+' · '+id:id})),...[...live?.expressions?.keys()||[]].map(name=>({id:'expression:'+name,label:'Expression · '+name}))];
}
export function autoFaceMapping(live){
    const targets=faceMappingTargets(live),mapping={};
    for(const name of FACE_SIGNALS){const target=targets.find(t=>matches[name].test(t.id+' '+t.label));if(target)mapping[name]=target.id;}
    // ParamCheek is normally blush. Never assign it to puff automatically.
    return mapping;
}
export function applyFaceMappings(live,signals,mapping,active){
    const core=live.avatar.internalModel.coreModel;
    live._faceSignalWeights||={};live._faceSignalExpressions||=new Set();
    live._faceSignalParameters||=new Set();
    const parameters=new Map(),expressions=new Map();
    for(const signal of FACE_SIGNALS){
        const target=mapping?.[signal];if(!target||target==='none')continue;
        const value=Number(signals?.[signal]),desired=active&&Number.isFinite(value)?Math.max(0,Math.min(1,value)):0;
        const weight=(live._faceSignalWeights[signal]||0)+(desired-(live._faceSignalWeights[signal]||0))*.4;live._faceSignalWeights[signal]=weight;
        const bucket=target.startsWith('expression:')?expressions:parameters;bucket.set(target,Math.max(bucket.get(target)||0,weight));
    }
    for(const id of live._faceSignalParameters)if(!parameters.has(id)){const index=core.getParameterIndex(id);if(index>=0)core.setParameterValueById(id,core.getParameterDefaultValue?.(index)??0);}
    live._faceSignalParameters.clear();
    for(const [id,value]of parameters){const index=core.getParameterIndex(id);if(index<0)continue;live._faceSignalParameters.add(id);
        const min=core.getParameterMinimumValue?.(index)??0,max=core.getParameterMaximumValue?.(index)??1,neutral=core.getParameterDefaultValue?.(index)??0;
        core.setParameterValueById(id,Math.max(min,Math.min(max,neutral+(max-neutral)*value)));
    }
    for(const name of live._faceSignalExpressions){if(!expressions.has('expression:'+name)&&!live.owner.manualExpressions?.has(name))live.removeExpression(name);}
    live._faceSignalExpressions.clear();
    for(const [id,value]of expressions){const name=id.slice(11);if(live.owner.manualExpressions?.has(name))continue;
        if(value>.005){live.setExpression(name,value);live._faceSignalExpressions.add(name);}else live.removeExpression(name);
    }
}
export function installLive2DFaceMapping(getViewer,getKey){
    const container=document.getElementById('live2d-face-mappings'),list=document.getElementById('live2d-face-mapping-list'),status=document.getElementById('live2d-face-mapping-status');
    let live=null,key='',mapping={};const save=()=>localStorage.setItem('sakura_live2d_face_mapping:'+key,JSON.stringify(mapping));
    function refresh(){live=getViewer()?.live2d;container.hidden=!live;if(!live)return;key=getKey();
        try{mapping=JSON.parse(localStorage.getItem('sakura_live2d_face_mapping:'+key)||'null')||autoFaceMapping(live);}catch(_){mapping=autoFaceMapping(live);}
        live.faceSignalMapping=mapping;list.replaceChildren();const targets=faceMappingTargets(live);
        for(const signal of FACE_SIGNALS){const label=document.createElement('label');label.textContent=signal;const select=document.createElement('select');select.add(new Option('Not mapped','none'));for(const target of targets)select.add(new Option(target.label,target.id));select.value=mapping[signal]||'none';select.onchange=()=>{mapping[signal]=select.value;live.faceSignalMapping=mapping;save();};label.append(select);list.append(label);}
        status.textContent='Map each signal to an authored parameter or expression. Cheek puff needs native SDK input; it is not estimated from a smile.';
    }
    document.getElementById('live2d-face-mapping-reset').onclick=()=>{localStorage.removeItem('sakura_live2d_face_mapping:'+key);refresh();};
    document.getElementById('live2d-puff-preview').oninput=e=>{if(!live)return;live.faceSignalPreview={cheekPuff:Number(e.target.value)/100};status.textContent='Manual cheek-puff preview. This is not camera detection.';};
    document.getElementById('live2d-puff-preview-stop').onclick=()=>{if(live)live.faceSignalPreview=null;document.getElementById('live2d-puff-preview').value=0;};
    return{refresh,stop(){if(live)live.faceSignalPreview=null;}};
}
