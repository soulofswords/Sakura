export function modelRepairKey(url){
    let key=String(url).split(/[?#]/,1)[0];
    if(/^https?:\/\//i.test(key))key=new URL(key).pathname;
    if(key.startsWith('/models/'))key=decodeURIComponent(key.slice(8));
    return key.replace(/\\/g,'/');
}

export default class ModelRepairStore {
    constructor(){this.records=new Map();this.queue=Promise.resolve();}
    key(url){return modelRepairKey(url);}
    async load(url,isCurrent=()=>true){
        const key=modelRepairKey(url);let result;
        try{
            const response=await fetch('/api/models/bone-repairs?model='+encodeURIComponent(key),{cache:'no-store',signal:AbortSignal.timeout(10000)});
            result=await response.json();if(!response.ok)throw Error(result.error||'Bone repairs could not be read.');
        }catch(error){console.warn('Persistent bone repairs unavailable:',error);}
        if(!isCurrent())return;
        const record=result?.repairs||{manual:[],diagnostic:null};
        if(!result?.repairs&&!result?.invalidated){
            try{
                record.manual=JSON.parse(localStorage.getItem('sakura_disabled_bones:'+key)||'[]');
                for(const candidate of [url.split(/[?#]/,1)[0],'/models/'+key,'/models/'+key.split('/').map(encodeURIComponent).join('/')]){
                    const legacy=JSON.parse(localStorage.getItem('sakura_rig_analysis:'+candidate)||'null');if(legacy){record.diagnostic=legacy;break;}
                }
            }catch(_){}
        }
        if(!Array.isArray(record.manual))record.manual=[];
        this.records.set(key,record);
        // Migrate existing browser repairs without changing their rig signature.
        if(result&&!result.repairs&&!result.invalidated&&(record.manual.length||record.diagnostic))void this.save(key).catch(console.warn);
    }
    diagnostic(url){return this.records.get(modelRepairKey(url))?.diagnostic;}
    manual(url){return this.records.get(modelRepairKey(url))?.manual||[];}
    saveDiagnostic(url,report){const key=modelRepairKey(url),record=this.records.get(key)||{manual:[]};record.diagnostic=report?{version:report.version||2,signature:report.signature,frozen:[...report.frozen]}:null;this.records.set(key,record);return this.save(key);}
    saveManual(url,manual){const key=modelRepairKey(url),record=this.records.get(key)||{diagnostic:null};record.manual=[...manual];this.records.set(key,record);return this.save(key);}
    save(key){
        const body=JSON.stringify({model:key,repairs:this.records.get(key)});
        const write=async()=>{
            const response=await fetch('/api/models/bone-repairs',{method:'POST',headers:{'Content-Type':'application/json'},body,
                keepalive:body.length<60000,signal:AbortSignal.timeout(10000)});
            const data=await response.json();if(!response.ok||!data.saved)throw Error(data.error||'Bone repairs could not be saved.');
        };
        const pending=this.queue.then(write,write);this.queue=pending.catch(()=>{});return pending;
    }
}
