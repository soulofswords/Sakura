import {nativeJob} from './native-jobs.js';
let sequence=0;
export function installProviderTools(parent,{provider,key,model,voice,address,status,onSaved=()=>{}}){
    const id='provider-models-'+(++sequence),options=document.createElement('datalist');options.id=id;model.setAttribute('list',id);parent.append(options);
    const choose=document.createElement('select');choose.hidden=true;choose.setAttribute('aria-label','Available chat models');parent.append(choose);
    const row=document.createElement('nav'),discover=document.createElement('button'),check=document.createElement('button');
    discover.type=check.type='button';discover.textContent='Find available models';check.textContent='Test API (small request)';row.append(discover,check);parent.append(row);
    const help=document.createElement('small');help.textContent='Model discovery does not prove chat quota. Test API sends one small generation request and may use paid API credit. No voice request is sent.';parent.append(help);
    function save(){
        const previous=JSON.parse(Sakura.localConfig());
        if(!key.value.trim()&&(!previous.key_set||previous.provider!==provider.value))throw Error('Enter a key issued by the selected provider.');
        const result=JSON.parse(Sakura.configureLocal(provider.value,key.value.trim(),model.value.trim(),voice.value,typeof address==='function'?address():address.value));
        if(result.error)throw Error(result.error);key.value='';key.placeholder='Saved securely · leave blank to keep';onSaved(result);return result;
    }
    async function run(button,method){
        if(discover.disabled||check.disabled)return;
        const label=button.textContent;discover.disabled=check.disabled=true;button.setAttribute('aria-busy','true');button.textContent=method==='modelCatalog'?'Finding models…':'Testing API…';
        try{
            const config=save();status(method==='modelCatalog'?'Finding models available to your key…':'Sending one small API test request…');
            const result=await nativeJob(method);
            if(method==='modelCatalog'){
                options.replaceChildren(...(result.models||[]).map(id=>{const item=document.createElement('option');item.value=id;return item;}));
                choose.replaceChildren(...(result.models||[]).map(id=>{const item=document.createElement('option');item.value=id;item.textContent=id;return item;}));
                if(!options.children.length)throw Error('No compatible chat models were listed for this key. Check project access.');
                // Keep the user's explicit model if listed; otherwise choose a listed low-latency model.
                if(!result.models.includes(model.value)){
                    const preferred=config.provider==='gemini'?result.models.find(id=>/flash/.test(id)&&!/preview|exp/.test(id)):result.models.find(id=>id==='gpt-4.1-mini');
                    model.value=preferred||result.models[0];save();
                }
                choose.value=model.value;choose.hidden=false;
                status(options.children.length+' models found. Selected '+model.value+'. Choose a model below, then Test API.');
            }else status(result.message||'API test Passed');
        }catch(error){status(error.message);}finally{discover.disabled=check.disabled=false;button.removeAttribute('aria-busy');button.textContent=label;}
    }
    discover.onclick=()=>run(discover,'modelCatalog');check.onclick=()=>run(check,'checkLocalApi');
    choose.onchange=()=>{model.value=choose.value;try{save();status('Saved '+model.value+'. Test API to check generation access.');}catch(error){status(error.message);}};
    provider.addEventListener('change',()=>{options.replaceChildren();choose.replaceChildren();choose.hidden=true;});
}
