// Renderer frames have a separate origin and no privileged Sakura interface.
export const RENDER_ORIGIN='https://models.sakura.invalid';
const frames=new WeakMap();
let sequence=0;
function entry(frame){
    if(frames.has(frame))return frames.get(frame);
    const state={ready:false,error:'',pending:new Map(),api:{}};
    function send(method,args,wait){
        if(method==='startTracking')window.Sakura.rendererCamera(true);
        if(method==='stopTracking'||method==='load'||(method==='pause'&&args[0]))window.Sakura.rendererCamera(false);
        if(!wait){frame.contentWindow?.postMessage({type:'avatar-call',method,args},RENDER_ORIGIN);return;}
        return new Promise((resolve,reject)=>{
            const id='avatar-'+(++sequence),timer=setTimeout(()=>{state.pending.delete(id);reject(Error('Model renderer timed out.'));},60000);
            state.pending.set(id,{resolve,reject,timer});
            frame.contentWindow?.postMessage({type:'avatar-call',id,method,args},RENDER_ORIGIN);
        });
    }
    for(const method of ['load','startTracking','speak'])state.api[method]=(...args)=>send(method,args,true);
    for(const method of ['stopTracking','calibrate','hands','stop','pause'])state.api[method]=(...args)=>send(method,args,false);
    window.addEventListener('message',event=>{
        if(event.origin!==RENDER_ORIGIN||event.source!==frame.contentWindow)return;
        const data=event.data;
        if(data?.type==='avatar-ready'){
            state.ready=true;state.error='';
            let mode='system';try{mode=localStorage.getItem('sakura_ui_theme')||mode;}catch(_){}
            frame.contentWindow.postMessage({type:'sakura-appearance',mode},RENDER_ORIGIN);return;
        }
        if(data?.type==='avatar-error'){state.error=String(data.error||'Model renderer unavailable.');return;}
        if(data?.type!=='avatar-reply')return;
        const job=state.pending.get(data.id);if(!job)return;
        state.pending.delete(data.id);clearTimeout(job.timer);
        if(data.error){window.Sakura.rendererCamera(false);job.reject(Error(String(data.error)));}else job.resolve(data.result);
    });
    frame.addEventListener('load',()=>{state.ready=false;frame.contentWindow?.postMessage({type:'avatar-ping'},RENDER_ORIGIN);});
    frames.set(frame,state);return state;
}
export function rendererFor(frame){if(!frame)return null;const state=entry(frame);return state.ready?state.api:null;}
export async function openRenderer(frame){
    const state=entry(frame);
    if(!frame.getAttribute('src'))frame.src=RENDER_ORIGIN+'/local-viewer.html';
    const deadline=Date.now()+30000;
    while(!state.ready){
        if(state.error)throw Error(state.error);
        if(Date.now()>deadline)throw Error('Model renderer did not start. Update Android System WebView.');
        frame.contentWindow?.postMessage({type:'avatar-ping'},RENDER_ORIGIN);
        await new Promise(resolve=>setTimeout(resolve,100));
    }
    return state.api;
}
