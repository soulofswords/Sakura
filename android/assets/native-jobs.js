const pending=new Map();
let sequence=0;
window.sakuraNativeReply=(id,result)=>{
    const job=pending.get(id);if(!job)return;
    pending.delete(id);clearTimeout(job.timer);
    if(result?.error)job.reject(Error(result.error));else job.resolve(result);
};
export function nativeJob(method,...args){
    return new Promise((resolve,reject)=>{
        const id='phone-'+Date.now()+'-'+(++sequence);
        const timer=setTimeout(()=>{pending.delete(id);reject(Error('Request timed out. Check your connection and try again.'));},160000);
        pending.set(id,{resolve,reject,timer});
        try{window.Sakura[method](id,...args);}catch(error){clearTimeout(timer);pending.delete(id);reject(error);}
    });
}
