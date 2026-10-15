// Screen permission controls sampling. Notes are silent, bounded, and RAM-only.
export default class ScreenMemory {
    constructor(share,active,busy,request=fetch){
        this.share=share;this.active=active;this.busy=busy;this.request=request;
        this.lastRun=-Infinity;this.pending=false;this.controller=null;
    }
    async tick(){
        if(!this.active()||!this.share.enabled){this.controller?.abort();return;}
        if(this.pending||this.busy()||Date.now()-this.lastRun<20000)return;
        const frames=this.share.observationFrames();if(!frames.length)return;
        this.pending=true;this.lastRun=Date.now();
        const controller=new AbortController();this.controller=controller;
        const timeout=setTimeout(()=>controller.abort(),18000);
        try{
            await this.request('/api/chat',{method:'POST',signal:controller.signal,
                headers:{'Content-Type':'application/json'},body:JSON.stringify({screen_observation:true,
                    text:'Silent screen timeline observation',screen_image:frames.at(-1),screen_frames:frames,defer_audio:true})});
        }catch(_){}finally{clearTimeout(timeout);this.pending=false;if(this.controller===controller)this.controller=null;}
    }
    stop(){this.controller?.abort();}
}
