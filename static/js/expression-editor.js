import {installCustomExpressions} from './custom-expressions.js?v=1';
export function hotkeyFor(event) {
    if (!event.code || ['ControlLeft','ControlRight','ShiftLeft','ShiftRight','AltLeft','AltRight','MetaLeft','MetaRight'].includes(event.code)) return '';
    return [event.ctrlKey?'Ctrl':'',event.altKey?'Alt':'',event.shiftKey?'Shift':'',event.metaKey?'Meta':'',event.code].filter(Boolean).join('+');
}

export function installExpressionEditor(getViewer, getModelKey) {
    const panel=document.getElementById('expression-modal'),list=document.getElementById('expression-list');
    const status=document.getElementById('expression-status');
    let recordingName=null;
    let customEditor=null;
    const key=()=> 'sakura_expression_bindings:'+getModelKey();
    const bindings=()=> {
        try {
            const data=JSON.parse(localStorage.getItem(key())||'{}');
            return Object.fromEntries(Object.entries(data||{}).filter(([,binding])=>binding &&
                (typeof binding.hotkey==='string'||binding.hotkey===null) && Number.isFinite(binding.weight) && binding.weight>=0 && binding.weight<=1));
        } catch(_) { return {}; }
    };
    const save=data=>localStorage.setItem(key(),JSON.stringify(data));
    const defaultHotkey=index=>{
        const keys=['1','2','3','4','5','6','7','8','9','0'];
        return `Ctrl+${Math.floor(index/keys.length)?'Alt+':''}Digit${keys[index%keys.length]}`;
    };
    const ensureDefaults=names=>{
        const data=bindings(),used=new Set(Object.values(data).map(binding=>binding.hotkey).filter(Boolean));
        let changed=false;
        names.forEach((name,index)=>{
            if(Object.hasOwn(data,name))return;
            let hotkey=defaultHotkey(index),offset=0;
            while(used.has(hotkey)&&offset<names.length){hotkey=defaultHotkey(index+(++offset));}
            data[name]={hotkey,weight:1};used.add(hotkey);changed=true;
        });
        if(changed)save(data);
        return data;
    };
    const apply=(name,weight)=>{
        const v=getViewer();if(!v?.vtuberTrackingMode||!v.allMorphNames.includes(name))return;
        v.manualExpressions ||= new Map();v.manualExpressions.set(name,weight);v.manualExpression={name,weight};
        if(v.live2d&&!v.live2d.setExpression(name,weight)){
            v.manualExpressions.delete(name);v.manualExpression=null;status.textContent='This Live2D expression could not be applied.';return;
        }
        status.textContent='Active expressions: '+[...v.manualExpressions.keys()].join(', ');
    };
    const deactivate=name=>{
        const v=getViewer();v?.manualExpressions?.delete(name);
        for(const p of v?.customExpressions?.[name]?.parameters||[])if(!v?.live2d)v?.setMorph?.(p.id,0);
        if(v?.live2d)v.live2d.removeExpression(name);else v?.setMorph?.(name,0);
        if(v?.manualExpression?.name===name)v.manualExpression=null;
        status.textContent='Expression turned off: '+name;
    };
    const updateShortcut=(name,label)=>{
        const binding=bindings()[name];label.textContent=binding?.hotkey||'No shortcut';
    };
    const render=()=>{
        customEditor?.register();
        recordingName=null;list.replaceChildren();
        const names=getViewer()?.allMorphNames||[],data=ensureDefaults(names);
        for(const name of names){
            const binding=data[name]||{hotkey:null,weight:1};
            const card=document.createElement('section');card.className='expression-card';card.dataset.expression=name;
            const header=document.createElement('div');header.className='expression-card-header';
            const title=document.createElement('strong');title.className='expression-card-name';title.textContent=binding.label||getViewer()?.customExpressions?.[name]?.name||name;
            const shortcut=document.createElement('span');shortcut.className='expression-shortcut';shortcut.textContent=binding.hotkey||'No shortcut';
            header.append(title,shortcut);
            const strengthLabel=document.createElement('label');strengthLabel.textContent='Strength';
            const strength=document.createElement('input');strength.type='range';strength.min='0';strength.max='100';strength.value=Math.round(binding.weight*100);strength.setAttribute('aria-label',`${name} expression strength`);
            strength.oninput=()=>{
                const current=bindings();current[name]={...(current[name]||{}),weight:Number(strength.value)/100};save(current);
                if(getViewer()?.manualExpressions?.has(name)){
                    getViewer().manualExpressions.set(name,Number(strength.value)/100);
                    if(getViewer().manualExpression?.name===name)getViewer().manualExpression.weight=Number(strength.value)/100;
                    if(getViewer().live2d)getViewer().live2d.setExpression(name,Number(strength.value)/100);
                }
            };
            const actions=document.createElement('div');actions.className='expression-card-actions';
            const preview=document.createElement('button');preview.type='button';preview.textContent='Preview';preview.onclick=()=>apply(name,Number(strength.value)/100);
            const assign=document.createElement('button');assign.type='button';assign.textContent='Set hotkey';assign.onclick=()=>{recordingName=name;status.textContent=`Press a shortcut for ${name}…`;};
            const remove=document.createElement('button');remove.type='button';remove.textContent='Clear hotkey';remove.onclick=()=>{const current=bindings();current[name]={...current[name],hotkey:null,weight:Number(strength.value)/100};save(current);updateShortcut(name,shortcut);};
            const off=document.createElement('button');off.type='button';off.textContent='Turn off';off.onclick=()=>deactivate(name);
            actions.append(preview,assign,remove,off);card.append(header,strengthLabel,strength,actions);list.append(card);
            const rename=document.createElement('input');rename.type='text';rename.maxLength=100;rename.value=title.textContent;rename.setAttribute('aria-label','Expression name');
            const renameButton=document.createElement('button');renameButton.type='button';renameButton.textContent='Rename';renameButton.onclick=()=>{const label=rename.value.trim();if(!label)return;const current=bindings();current[name]={...current[name],label};save(current);title.textContent=label;};
            const naming=document.createElement('div');naming.className='expression-card-actions';naming.append(rename,renameButton);card.append(naming);
            if(name.startsWith('custom:')){const edit=document.createElement('button');edit.textContent='Edit';edit.onclick=()=>customEditor.open(name);const deletion=document.createElement('button');deletion.textContent='Delete custom';deletion.onclick=()=>{deactivate(name);customEditor.remove(name);};naming.append(edit,deletion);}
        }
        status.textContent=names.length?`${names.length} imported expressions. Shortcuts work while Sakura has focus.`:'No supported expressions in the loaded model.';
    };
    customEditor=installCustomExpressions(getViewer,getModelKey,render);
    document.getElementById('expression-editor-btn').onclick=()=>{render();panel.classList.remove('hidden');};
    document.getElementById('close-expression-modal').onclick=()=>{recordingName=null;customEditor.clearPreview();panel.classList.add('hidden');};
    document.getElementById('expression-neutral').onclick=()=>{const v=getViewer();v?.clearManualExpression();v?.manualExpressions?.clear();status.textContent='All active expressions cleared.';};
    window.addEventListener('keydown',event=>{
        const v=getViewer();if(!v?.vtuberTrackingMode||event.repeat)return;
        if(!recordingName&&(event.target.closest?.('input,textarea,select,[contenteditable="true"]')||!panel.classList.contains('hidden')))return;
        const code=hotkeyFor(event);if(!code)return;
        if(recordingName){
            event.preventDefault();event.stopImmediatePropagation();
            if(code==='Escape'){recordingName=null;status.textContent='Shortcut assignment cancelled.';return;}
            if(['Ctrl+Shift+KeyT','Ctrl+Shift+KeyH','Tab'].includes(code)){status.textContent='That shortcut is reserved. Choose another.';return;}
            const data=bindings();
            for(const [name,binding]of Object.entries(data))if(binding.hotkey===code)data[name]={...binding,hotkey:null};
            const card=[...list.children].find(item=>item.dataset.expression===recordingName);
            data[recordingName]={...data[recordingName],hotkey:code,weight:Number(card?.querySelector('input')?.value??100)/100};
            save(data);recordingName=null;render();status.textContent=`Shortcut assigned: ${code}`;return;
        }
        const entry=Object.entries(bindings()).find(([name,binding])=>binding.hotkey===code&&v.allMorphNames.includes(name));
        if(!entry)return;
        event.preventDefault();event.stopImmediatePropagation();
        if(v.manualExpressions?.has(entry[0]))deactivate(entry[0]);else apply(entry[0],entry[1].weight);
    },true);
    return {refresh:render};
}
