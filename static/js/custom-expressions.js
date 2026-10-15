export function installCustomExpressions(getViewer,getKey,refreshCards) {
    const form=document.getElementById('custom-expression-editor'),rows=document.getElementById('custom-expression-parameters');
    const name=document.getElementById('custom-expression-name'),search=document.getElementById('custom-expression-search'),status=document.getElementById('expression-status');
    let editing=null,draft={},modelKey=null,parameters=[];
    const key=()=> 'sakura_custom_expressions:'+getKey();
    const read=()=>{try{const data=JSON.parse(localStorage.getItem(key())||'{}');return data&&typeof data==='object'&&!Array.isArray(data)?data:{};}catch(_){return {};}};
    const previewId='custom:preview';
    function clearPreview(){const v=getViewer();v?.manualExpressions?.delete(previewId);v?.live2d?.removeExpression?.(previewId);for(const p of v?.customExpressions?.[previewId]?.parameters||[])if(!v?.live2d)v?.setMorph?.(p.id,0);delete v?.customExpressions?.[previewId];v?.live2d?.expressions?.delete(previewId);}
    function register(){
        const v=getViewer();if(!v)return;
        v.customExpressions=read();
        v.allMorphNames=(v.allMorphNames||[]).filter(id=>!id.startsWith('custom:'));
        for(const [id,expression]of Object.entries(v.customExpressions)){
            if(!id.startsWith('custom:')||!expression||!Array.isArray(expression.parameters))continue;
            v.allMorphNames.push(id);
            if(v.live2d)v.live2d.expressions.set(id,{Type:'Live2D Expression',Parameters:expression.parameters.map(p=>({Id:p.id,Value:p.value,Blend:'Overwrite'}))});
        }
        if(modelKey!==getKey()){form.classList.add('hidden');editing=null;draft={};modelKey=getKey();}
    }
    function renderRows(){
        rows.replaceChildren();const filter=search.value.toLowerCase();
        for(const p of parameters.filter(p=>p.id.toLowerCase().includes(filter))){
            const row=document.createElement('label');row.className='custom-expression-row';
            const enabled=document.createElement('input');enabled.type='checkbox';enabled.checked=Object.hasOwn(draft,p.id);
            const title=document.createElement('span');title.textContent=p.id;
            const slider=document.createElement('input');slider.type='range';slider.min=p.min;slider.max=p.max;slider.step=(p.max-p.min)/200||.01;slider.value=draft[p.id]??p.value;slider.disabled=!enabled.checked;
            const number=document.createElement('input');number.type='number';number.min=p.min;number.max=p.max;number.step=slider.step;number.value=slider.value;number.disabled=slider.disabled;
            const change=value=>{const next=Number(value);if(!Number.isFinite(next))return;draft[p.id]=Math.max(p.min,Math.min(p.max,next));slider.value=number.value=draft[p.id];};
            enabled.onchange=()=>{slider.disabled=number.disabled=!enabled.checked;if(enabled.checked)change(slider.value);else delete draft[p.id];};
            slider.oninput=()=>change(slider.value);number.oninput=()=>change(number.value);
            row.append(enabled,title,slider,number);rows.append(row);
        }
    }
    function open(id=null){
        clearPreview();const v=getViewer();editing=id;const saved=id?read()[id]:null;name.value=saved?.name||'';draft=Object.fromEntries((saved?.parameters||[]).map(p=>[p.id,p.value]));search.value='';
        if(v?.live2d){const core=v.live2d.avatar.internalModel.coreModel,raw=core._model.parameters;
            parameters=Array.from(raw.ids,(id,i)=>({id,min:raw.minimumValues[i],max:raw.maximumValues[i],value:core.getParameterValueByIndex(i)}));
        }else parameters=(v?.allMorphNames||[]).filter(id=>!id.startsWith('custom:')).map(id=>({id,min:0,max:1,value:0}));
        form.classList.remove('hidden');renderRows();
    }
    const definition=()=>({name:name.value.trim(),parameters:Object.entries(draft).map(([id,value])=>({id,value}))});
    search.oninput=renderRows;
    document.getElementById('custom-expression-new').onclick=()=>open();
    document.getElementById('custom-expression-cancel').onclick=()=>{clearPreview();form.classList.add('hidden');};
    document.getElementById('custom-expression-preview').onclick=()=>{
        const v=getViewer();if(!v||v.areAiExpressionsAutomatic?.()){status.textContent='Turn Reactions off to preview expressions manually.';return;}
        clearPreview();const expression=definition();v.customExpressions ||= {};v.customExpressions[previewId]=expression;
        v.manualExpressions ||= new Map();v.manualExpressions.set(previewId,1);
        if(v.live2d){v.live2d.expressions.set(previewId,{Parameters:expression.parameters.map(p=>({Id:p.id,Value:p.value,Blend:'Overwrite'}))});v.live2d.setExpression(previewId,1);}
        status.textContent='Previewing custom expression. Cancel removes the preview.';
    };
    document.getElementById('custom-expression-save').onclick=()=>{
        const expression=definition();if(!expression.name||!expression.parameters.length){status.textContent='Enter a name and enable at least one parameter.';return;}
        clearPreview();const all=read(),id=editing||'custom:'+crypto.randomUUID();all[id]=expression;localStorage.setItem(key(),JSON.stringify(all));form.classList.add('hidden');register();refreshCards();status.textContent='Custom expression saved: '+expression.name;
    };
    function remove(id){const v=getViewer(),all=read();delete all[id];localStorage.setItem(key(),JSON.stringify(all));v?.manualExpressions?.delete(id);v?.live2d?.removeExpression(id);v?.live2d?.expressions.delete(id);register();refreshCards();}
    return {register,open,remove,clearPreview};
}
