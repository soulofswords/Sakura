// Wait asynchronously for the first complete draw before uncovering the canvas.
// compileAsync prepares programs, but texture/bone-buffer uploads happen on draw.
export async function waitForModelGpu(renderer,isCurrent,timeoutMs=5000){
    const gl=renderer.getContext();
    if(!isCurrent()||gl.isContextLost?.())return false;
    if(!gl.fenceSync||!gl.clientWaitSync)return true;
    const sync=gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE,0);
    if(!sync)return false;
    try{
        gl.flush();
        const started=performance.now();
        while(isCurrent()&&!gl.isContextLost?.()){
            const status=gl.clientWaitSync(sync,0,0);
            if(status===gl.ALREADY_SIGNALED||status===gl.CONDITION_SATISFIED)return true;
            if(status===gl.WAIT_FAILED)return false;
            if(performance.now()-started>=timeoutMs)return false;
            await new Promise(resolve=>setTimeout(resolve,8));
        }
        return false;
    }finally{gl.deleteSync(sync);}
}
