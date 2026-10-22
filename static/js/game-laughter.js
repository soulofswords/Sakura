export async function playGameLaughter(style,viewer,lipSync,isCurrent){
    if(!['laugh','laugh_bend'].includes(style)||!isCurrent()||viewer?.live2d||!viewer?.dance?.supported())return false;
    const model=viewer.model,clip=style==='laugh_bend'?'laugh-belly.wav':'laugh-short.wav';
    let started=false;
    try{
        await lipSync.playWithLipSync('/static/audio/reactions/'+clip+'?v=natural86',()=>{
            if(!isCurrent()||viewer.model!==model||viewer.live2d||!viewer.dance.supported()){
                lipSync.stop();return;
            }
            started=viewer.dance.start(style);
            if(!started)lipSync.stop();
        });
        if(started)viewer.dance.stop();
        return started;
    }catch(error){if(started)viewer.dance.stop();throw error;}
    finally{if(started&&(!isCurrent()||viewer.model!==model))viewer.dance.stop();}
}
